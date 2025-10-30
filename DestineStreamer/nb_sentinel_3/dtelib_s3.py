import gc
import json
from datetime import datetime
from typing import List, Optional

import notebook_stream_decoder.notebook_stream_decoder as ns
import requests
from requests import auth

API = "https://streamer.destine.eu/api/streaming/s3/data/metadata/{}"
# API = "http://127.0.0.1:8000/api/streaming/s3/data/metadata/{}"
START_QP = "start_date"
END_QP = "end_date"

API_DT_FORMAT = "%Y%m%dT%H%M"
FPS = 25


class BearerAuth(auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


class DTEStreamer_S3:
    def __init__(
        self,
        continent: str,
        start_date: datetime,
        end_date: datetime,
        token: str,
    ):
        self.continent: str = continent
        self.start_date: Optional[datetime] = start_date
        self.end_date: Optional[datetime] = end_date
        self.__stream_metadata: dict = dict()
        self.__frames_metadata: dict = dict()
        self.__frame_count: int = -1
        self.__start_img_number: int = -1
        self.__cur_frame_number = -1
        self.__rust_stream_iter = None

        self.token = token

        self.__get_stream_and_metadata()

        # seek to first data frame in the selected time span
        self.__seek_to_frame(self.__frames_metadata[0]["img_number"] - 1)

    def __get_stream_and_metadata(self):
        """
        This method fetches metadata and the path to the stream from the DTE API
        and stores it in the object. That data us used to access the stream,
        select frames and provide descriptive metadata for scaling the data
         represented in the stream.

        :return: None
        """

        try:
            params = dict()

            if self.start_date is not None:
                params[START_QP] = self.start_date.strftime(API_DT_FORMAT)

            if self.end_date is not None:
                params[END_QP] = self.end_date.strftime(API_DT_FORMAT)

            url = API.format(self.continent)
            response = requests.get(url=url, params=params, auth=BearerAuth(self.token))

            if response.status_code != 200:
                print(
                    f"API error {response.status_code}: {response.content.decode('utf-8')}"
                )
                raise SystemExit

            content = json.loads(response.content)

            # saving the uri of the stream according to the selected resolution.
            self.__stream_metadata = {
                key: value for key, value in content.items() if key != "images"
            }

            # saving metadata about the images:
            # date and time of image
            # min value for scale
            # max value for scale
            # frame number
            self.__frames_metadata = json.loads(response.content)["images"]

        except KeyError:
            raise ConnectionError("Stream not found")

        if (
            self.__stream_metadata is None
            or len(self.__stream_metadata) == 0
            or self.__frames_metadata is None
        ):
            print("No data found")
            raise SystemExit

        self.__frame_count = len(self.__frames_metadata)
        self.__start_img_number = self.__frames_metadata[0]["img_number"]

    def seek_to_date(self, date: datetime):
        """
        Binary Search Algorithm to find the frame that is at the specified time. If the exact date and time is
        not available, the one closest but prior to it will be used.
        """
        min_pos = 0
        max_pos = len(self.__frames_metadata) - 1
        chk_pos = int((min_pos + max_pos) / 2)

        # Is date in range?
        min_date = self.__frames_metadata[0]["img_start_date"]
        min_date = datetime.strptime(min_date, "%Y-%m-%dT%H:%M:%S")
        max_date = self.__frames_metadata[-1]["img_start_date"]
        max_date = datetime.strptime(max_date, "%Y-%m-%dT%H:%M:%S")

        if not (min_date <= date <= max_date):
            return False

        # If the date to seek to is equal to the max date in the list, the algorithm will not find it. It will
        # always take the penultimate date. Therefore this check has to be in place
        if date == max_date:
            self.__seek_to_frame(max_pos + (self.__start_img_number - 1))
            return True

        while True:
            img_date = self.__frames_metadata[chk_pos]["img_start_date"]
            img_date = datetime.strptime(img_date, "%Y-%m-%dT%H:%M:%S")

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
                img_date = self.__frames_metadata[chk_pos]["img_start_date"]
                img_date = datetime.strptime(img_date, "%Y-%m-%dT%H:%M:%S")
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

        ss_time = f"{self.__cur_frame_number / FPS:.2f}"
        stream_file = self.__stream_metadata["stream_path"]
        t_time = f"{(self.__frame_count - (self.__cur_frame_number - (self.__start_img_number - 1))) / FPS:.2f}"

        min_val = self.__cur_frame_metadata()["img_min_value"]
        max_val = self.__cur_frame_metadata()["img_max_value"]

        if self.__rust_stream_iter is not None:
            self.__rust_stream_iter.cleanup()
            del self.__rust_stream_iter
            self.__rust_stream_iter = None

        self.__rust_stream_iter = ns.StreamIter(
            nx=self.nx(),
            ny=self.ny(),
            stream_file=stream_file,
            min_val=min_val,
            max_val=max_val,
            ss_time=ss_time,
            t_time=t_time,
        )

    def __update_scaling(self):
        min_val = self.__cur_frame_metadata()["img_min_value"]
        max_val = self.__cur_frame_metadata()["img_max_value"]
        self.__rust_stream_iter.set_scaling(min_val, max_val)

    def load_next_image(self):
        while True:
            try:
                image = self.__rust_stream_iter.__next__()
            except StopIteration:
                break
            satellite = self.__cur_frame_metadata()["satellite"]
            img_date = self.__cur_frame_metadata()["img_start_date"]
            img_date = datetime.strptime(img_date, "%Y-%m-%dT%H:%M:%S")

            # don't scale next frame on last frame
            if self.__cur_frame_number < (
                (self.__start_img_number - 1) + self.__frame_count - 1
            ):
                self.__cur_frame_number += 1
                self.__update_scaling()

            yield (
                image,
                {
                    "img_date": img_date,
                    "satellite": satellite,
                },
            )
            gc.collect()

    def __cur_frame_metadata(self):
        return self.__frames_metadata[
            self.__cur_frame_number - (self.__start_img_number - 1)
        ]

    def nx(self) -> int:
        """
        This method returns number of datapoints in x dimension.

        :return: - nx (int)
        """
        return self.__stream_metadata["nx"]

    def ny(self) -> int:
        """
        This method returns number of datapoints in y dimension.

        :return: - ny (int)
        """
        return self.__stream_metadata["ny"]

    def bbox(self) -> List[float]:
        """
        This method returns the bounding box for the data dimension.

        :return: - bbox (list)
        """
        return self.__stream_metadata["bbox"]
