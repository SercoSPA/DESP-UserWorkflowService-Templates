import gc
from datetime import datetime
from itertools import product
from typing import List, Optional

import notebook_stream_decoder_geohash.notebook_stream_decoder_geohash as ns
import numpy as np
import requests
import shapely
from shapely.geometry import shape

API_GEOHASH_INFO = "https://streamer.destine.eu/api/streaming/s3/geohash/info/{}"
API_GEOHASH_METADATA = (
    "https://streamer.destine.eu/api/streaming/s3/geohash/metadata/{}"
)
START_QP = "start_date"
END_QP = "end_date"

FPS = 25

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def _geohash_decode_bbox(geohash: str):
    min_lat, max_lat = -90.0, 90.0
    min_lon, max_lon = -180.0, 180.0
    is_lon = True
    for char in geohash:
        bits = _BASE32.index(char)
        for i in range(4, -1, -1):
            bit = (bits >> i) & 1
            if is_lon:
                mid = (min_lon + max_lon) / 2
                min_lon, max_lon = (mid, max_lon) if bit else (min_lon, mid)
            else:
                mid = (min_lat + max_lat) / 2
                min_lat, max_lat = (mid, max_lat) if bit else (min_lat, mid)
            is_lon = not is_lon
    return min_lon, min_lat, max_lon, max_lat


def geohashes_for_aoi(aoi: dict, precision: int = 2) -> List[str]:
    geometry = aoi if aoi.get("type") != "Feature" else aoi["geometry"]
    aoi_min_lon, aoi_min_lat, aoi_max_lon, aoi_max_lat = shape(geometry).bounds
    result = []
    for chars in product(_BASE32, repeat=precision):
        gh = "".join(chars)
        gh_min_lon, gh_min_lat, gh_max_lon, gh_max_lat = _geohash_decode_bbox(gh)
        if (
            gh_min_lon < aoi_max_lon
            and gh_max_lon > aoi_min_lon
            and gh_min_lat < aoi_max_lat
            and gh_max_lat > aoi_min_lat
        ):
            result.append(gh)
    return result


def _geohash_grid_positions(geohashes: List[str]) -> dict:
    bboxes = {gh: _geohash_decode_bbox(gh) for gh in geohashes}
    unique_lons = sorted(
        {b[0] for b in bboxes.values()}
    )  # west → east  = col 0, 1, 2 …
    unique_lats = sorted(
        {b[1] for b in bboxes.values()}, reverse=True
    )  # north → south = row 0, 1, 2 …
    return {
        gh: (unique_lons.index(bbox[0]), unique_lats.index(bbox[1]))
        for gh, bbox in bboxes.items()
    }


def _rasterize_aoi(
    aoi: dict, geohashes: List[str], tile_nx: int, tile_ny: int
) -> np.ndarray:
    geometry = aoi if aoi.get("type") != "Feature" else aoi["geometry"]
    aoi_geom = shape(geometry)

    bboxes = [_geohash_decode_bbox(gh) for gh in geohashes]
    n_cols = len({b[0] for b in bboxes})
    n_rows = len({b[1] for b in bboxes})
    total_nx = n_cols * tile_nx
    total_ny = n_rows * tile_ny

    min_lon = min(b[0] for b in bboxes)
    max_lon = max(b[2] for b in bboxes)
    min_lat = min(b[1] for b in bboxes)
    max_lat = max(b[3] for b in bboxes)

    lon_per_pixel = (max_lon - min_lon) / total_nx
    lat_per_pixel = (max_lat - min_lat) / total_ny

    # pixel centre coordinates: row 0 = northernmost
    lons = min_lon + (np.arange(total_nx) + 0.5) * lon_per_pixel
    lats = max_lat - (np.arange(total_ny) + 0.5) * lat_per_pixel
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    mask = shapely.contains_xy(aoi_geom, lon_grid.ravel(), lat_grid.ravel())
    return mask.reshape(total_ny, total_nx).astype(np.uint8)


class DTEStreamer_S3_GH:
    def __init__(
        self,
        aoi: dict,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        self.aoi: dict = aoi
        self.geohashes: List[str] = geohashes_for_aoi(aoi)
        self.start_date: Optional[datetime] = start_date
        self.end_date: Optional[datetime] = end_date
        self.__streams: dict = {}
        self.__frames_metadata: list = []
        self.__frame_count: int = -1
        self.__start_img_number: int = -1
        self.__cur_frame_number = -1
        self.__multi_stream_iter = None
        self.__aoi_mask: Optional[np.ndarray] = None

        self.__get_stream_and_metadata()

        first_stream = next(iter(self.__streams.values()))
        self.__aoi_mask = _rasterize_aoi(
            self.aoi,
            self.geohashes,
            first_stream["tile_size_x"],
            first_stream["tile_size_y"],
        )

        # seek to first data frame in the selected time span
        self.__seek_to_frame(self.__frames_metadata[0]["image_number"] - 1)

    def __get_stream_and_metadata(self):
        params = {}
        if self.start_date is not None:
            params[START_QP] = self.start_date.isoformat()
        if self.end_date is not None:
            params[END_QP] = self.end_date.isoformat()

        for geohash in self.geohashes:
            response = requests.get(url=API_GEOHASH_INFO.format(geohash))
            if response.status_code != 200:
                print(
                    f"API error {response.status_code} for geohash {geohash}: {response.content.decode('utf-8')}"
                )
                raise SystemExit

            info = response.json()

            response = requests.get(
                url=API_GEOHASH_METADATA.format(info["stream_hash_id"]),
                params=params,
            )
            if response.status_code != 200:
                print(
                    f"API error {response.status_code} for stream {info['stream_hash_id']}: {response.content.decode('utf-8')}"
                )
                raise SystemExit

            images = response.json()["images"]

            self.__streams[geohash] = {
                "stream_hash_id": info["stream_hash_id"],
                "stream_url": info["stream_url"],
                "mask_url": info["mask_url"],
                "tile_size_x": info["tile_size_x"],
                "tile_size_y": info["tile_size_y"],
                "frames": {
                    img["image_number"]: {
                        "min_val": img["min_val"],
                        "max_val": img["max_val"],
                    }
                    for img in images
                },
            }

            this_frames = [
                {
                    "image_number": img["image_number"],
                    "sensing_start_time": img["sensing_start_time"],
                    "satellite": img["satellite"],
                }
                for img in images
            ]

            if not self.__frames_metadata:
                self.__frames_metadata = this_frames
            else:
                assert len(self.__frames_metadata) == len(
                    this_frames
                ), f"Frame count mismatch for geohash {geohash}"
                for a, b in zip(self.__frames_metadata, this_frames):
                    assert (
                        a["image_number"] == b["image_number"]
                    ), f"image_number mismatch for geohash {geohash}"
                    assert (
                        a["sensing_start_time"] == b["sensing_start_time"]
                    ), f"sensing_start_time mismatch at image {a['image_number']} for geohash {geohash}"
                    assert (
                        a["satellite"] == b["satellite"]
                    ), f"satellite mismatch at image {a['image_number']} for geohash {geohash}"

        if not self.__frames_metadata:
            print("No data found")
            raise SystemExit

        self.__frame_count = len(self.__frames_metadata)
        self.__start_img_number = self.__frames_metadata[0]["image_number"]

    def seek_to_date(self, date: datetime):
        """
        Binary Search Algorithm to find the frame that is at the specified time. If the exact date and time is
        not available, the one closest but prior to it will be used.
        """
        min_pos = 0
        max_pos = len(self.__frames_metadata) - 1
        chk_pos = int((min_pos + max_pos) / 2)

        # Is date in range?
        min_date = datetime.strptime(
            self.__frames_metadata[0]["sensing_start_time"], "%Y-%m-%dT%H:%M:%S"
        )
        max_date = datetime.strptime(
            self.__frames_metadata[-1]["sensing_start_time"], "%Y-%m-%dT%H:%M:%S"
        )

        if not (min_date <= date <= max_date):
            return False

        # If the date to seek to is equal to the max date in the list, the algorithm will not find it. It will
        # always take the penultimate date. Therefore this check has to be in place
        if date == max_date:
            self.__seek_to_frame(max_pos + (self.__start_img_number - 1))
            return True

        while True:
            img_date = datetime.strptime(
                self.__frames_metadata[chk_pos]["sensing_start_time"],
                "%Y-%m-%dT%H:%M:%S",
            )

            if img_date > date:
                max_pos = chk_pos
                chk_pos = int((min_pos + max_pos) / 2)
            elif img_date < date:
                min_pos = chk_pos
                chk_pos = int((min_pos + max_pos) / 2)
            else:
                self.__seek_to_frame(chk_pos + (self.__start_img_number - 1))
                return True

            # Here, case min_pos and max_pos are neighbors and the date to seek to is not in the list.
            # In this case, take the closest previous date closest date provided, which is min_pos.
            if min_pos == chk_pos:
                self.__seek_to_frame(chk_pos + (self.__start_img_number - 1))
                return True

    def __seek_to_frame(self, frame_number=0):
        if (
            not self.__start_img_number - 1
            <= frame_number
            < (self.__start_img_number - 1) + self.__frame_count
        ):
            raise IndexError(
                f"Frame number {frame_number} out of bounds [{self.__start_img_number}: "
                + f"{(self.__start_img_number - 1) + self.__frame_count - 1}]"
            )
        self.__cur_frame_number = frame_number

        seek_pos = frame_number - (self.__start_img_number - 1)
        ss_time = f"{frame_number / FPS:.2f}"
        t_time = f"{(self.__frame_count - seek_pos) / FPS:.2f}"

        if self.__multi_stream_iter is not None:
            self.__multi_stream_iter.cleanup()
            self.__multi_stream_iter = None

        positions = _geohash_grid_positions(self.geohashes)
        geohashes_ordered = list(self.__streams.keys())
        remaining_frames = self.__frames_metadata[seek_pos:]
        first_stream = next(iter(self.__streams.values()))

        self.__multi_stream_iter = ns.MultiStreamIter(
            stream_urls=[self.__streams[gh]["stream_url"] for gh in geohashes_ordered],
            mask_urls=[self.__streams[gh]["mask_url"] for gh in geohashes_ordered],
            col_indices=[positions[gh][0] for gh in geohashes_ordered],
            row_indices=[positions[gh][1] for gh in geohashes_ordered],
            n_cols=len({_geohash_decode_bbox(gh)[0] for gh in self.geohashes}),
            n_rows=len({_geohash_decode_bbox(gh)[1] for gh in self.geohashes}),
            tile_nx=first_stream["tile_size_x"],
            tile_ny=first_stream["tile_size_y"],
            min_vals=[
                [
                    self.__streams[gh]["frames"][f["image_number"]]["min_val"]
                    for f in remaining_frames
                ]
                for gh in geohashes_ordered
            ],
            max_vals=[
                [
                    self.__streams[gh]["frames"][f["image_number"]]["max_val"]
                    for f in remaining_frames
                ]
                for gh in geohashes_ordered
            ],
            ss_time=ss_time,
            t_time=t_time,
            aoi_mask=self.__aoi_mask,
        )

    def load_next_image(self):
        while True:
            try:
                mosaic = next(self.__multi_stream_iter)
            except StopIteration:
                break

            metadata = self.__cur_frame_metadata()
            img_date = datetime.strptime(
                metadata["sensing_start_time"], "%Y-%m-%dT%H:%M:%S"
            )
            self.__cur_frame_number += 1

            yield (mosaic, {"img_date": img_date, "satellite": metadata["satellite"]})
            gc.collect()

    def __cur_frame_metadata(self):
        return self.__frames_metadata[
            self.__cur_frame_number - (self.__start_img_number - 1)
        ]

    def nx(self) -> int:
        """
        Returns total pixel width of the accumulated tile area.
        Counts unique tile columns across all geohashes and multiplies by single tile width.

        :return: - nx (int)
        """
        bboxes = [_geohash_decode_bbox(gh) for gh in self.geohashes]
        n_cols = len({b[0] for b in bboxes})
        return n_cols * next(iter(self.__streams.values()))["tile_size_x"]

    def ny(self) -> int:
        """
        Returns total pixel height of the accumulated tile area.
        Counts unique tile rows across all geohashes and multiplies by single tile height.

        :return: - ny (int)
        """
        bboxes = [_geohash_decode_bbox(gh) for gh in self.geohashes]
        n_rows = len({b[1] for b in bboxes})
        return n_rows * next(iter(self.__streams.values()))["tile_size_y"]

    def bbox(self) -> List[float]:
        """
        Returns the bounding box of the full accumulated tile area as [min_lon, min_lat, max_lon, max_lat].

        :return: - bbox (list)
        """
        bboxes = [_geohash_decode_bbox(gh) for gh in self.geohashes]
        return [
            min(b[0] for b in bboxes),
            min(b[1] for b in bboxes),
            max(b[2] for b in bboxes),
            max(b[3] for b in bboxes),
        ]
