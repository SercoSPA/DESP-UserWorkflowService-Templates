import json
from datetime import datetime

import IPython
import notebook_stream_decoder.notebook_stream_decoder as ns
import numpy as np
import requests
from requests import auth

API = "https://streamer.destine.eu/api/streaming/data/"
# API = "https://127.0.0.1:39720/api/streaming/data/"
STREAM_EP = "metadata/{program_subset}/{variable}/{start_date}/{end_date}"
OV_EP = "overview/"

API_DT_FORMAT = "%Y%m%dT%H%M"
FPS = 25


class BearerAuth(auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


class DTEStreamer:
    def __init__(
        self,
        program_subset: str,
        variable: str,
        start_date: datetime,
        end_date: datetime,
        token: str,
    ):
        self.program_subset: str = program_subset
        self.__variable: str = variable
        self.start_date: datetime = start_date
        self.end_date: datetime = end_date
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
            api_start_date = self.start_date.strftime(API_DT_FORMAT)
            api_end_date = self.end_date.strftime(API_DT_FORMAT)

            url = API + STREAM_EP.format(
                program_subset=self.program_subset,
                variable=self.__variable,
                start_date=api_start_date,
                end_date=api_end_date,
            )
            response = requests.get(url=url, auth=BearerAuth(self.token))

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
        min_date = self.__frames_metadata[0]["img_date"]
        min_date = datetime.strptime(min_date, "%Y-%m-%dT%H:%M:%S")
        max_date = self.__frames_metadata[-1]["img_date"]
        max_date = datetime.strptime(max_date, "%Y-%m-%dT%H:%M:%S")

        if not (min_date <= date <= max_date):
            # raise IndexError(f"date out of bounds: {date.strftime('%Y-%m-%dT%H:%M:%S')}")
            return False

        # If the date to seek to is equal to the max date in the list, the algorithm will not find it. It will
        # always take the penultimate date. Therefore this check has to be in place
        if date == max_date:
            self.__seek_to_frame(max_pos + (self.__start_img_number - 1))
            return True

        while True:
            img_date = self.__frames_metadata[chk_pos]["img_date"]
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
                img_date = self.__frames_metadata[chk_pos]["img_date"]
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
        if self.__rust_stream_iter is not None:
            self.__rust_stream_iter.set_scaling(min_val, max_val)

    def load_next_image(self):
        if self.__rust_stream_iter is None:
            return

        self.__update_scaling()

        # for image in self.__rust_stream_iter:
        while True:
            try:
                image = self.__rust_stream_iter.__next__()
            except StopIteration:
                break

            img_date = self.__cur_frame_metadata()["img_date"]
            img_date = datetime.strptime(img_date, "%Y-%m-%dT%H:%M:%S")

            if self.program_subset.lower() != "climate dt":
                image = np.flipud(image)

            yield (image, img_date)

            # don't scale next frame on last frame
            if self.__cur_frame_number < (
                (self.__start_img_number - 1) + self.__frame_count - 1
            ):
                self.__cur_frame_number += 1
                self.__update_scaling()

    def __cur_frame_metadata(self):
        return self.__frames_metadata[
            self.__cur_frame_number - (self.__start_img_number - 1)
        ]

    def unit(self):
        """
        This method returns the unit of the data represented in the stream.

        :return: - unit (str)
        """
        return self.__stream_metadata["unit"]

    def name(self):
        """
        This method returns the name of the data represented in the stream.

        :return: - name (str)
        """
        return self.__stream_metadata["parameter_name"]

    def variable(self):
        """
        This method returns an abbreviated name of the data represented in the
        stream.

        :return: - variable (str)
        """
        return self.__stream_metadata["parameter_variable"]

    def type_of_level(self):
        """
        This method returns the type of level of the data represented in the
        stream.

        :return: - type_of_level (str)
        """
        return self.__stream_metadata["type_of_level"]

    def nx(self):
        """
        This method returns number of datapoints in x dimension.

        :return: - nx (int)
        """
        return self.__stream_metadata["nx"]

    def ny(self):
        """
        This method returns number of datapoints in y dimension.

        :return: - ny (int)
        """
        return self.__stream_metadata["ny"]

    def bbox(self):
        """
        This method returns the bounding box for the data dimension.

        :return: - bbox (list)
        """

        lons = [self.__stream_metadata["lon_start"], self.__stream_metadata["lon_end"]]
        lats = [self.__stream_metadata["lat_start"], self.__stream_metadata["lat_end"]]

        minx = min(lons)
        miny = max(lats)
        maxx = max(lons)
        maxy = min(lats)

        bbox = [minx, miny, maxx, maxy]
        return bbox


def get_stream_overview(token: str) -> IPython.display.TextDisplayObject:
    """
    This method fetches metadata for available data streams from the DTE API.
    The data is return as a table to overview accessible data.

    :return: - overview_table (IPython.display.TextDisplayObject)
    """
    try:
        url = API + OV_EP
        response = requests.get(url=url, auth=BearerAuth(token))
        response_content = json.loads(response.content)

        if response.status_code != 200:
            raise Exception(response_content)

        ov_table = ""

        for subset_name, subset_contents in response_content.items():
            ov_table += f"<h4>Program Subset: <b>{subset_name}</b></h4>"
            ov_table += "<table >"
            ov_table += table_row(
                variable="variable",
                title="title",
                period="period",
                compr="compression rate",
                ssim="SSIM",
                mre="mean relative error",
                st_st='<b style="align:left">',
                st_en="</b>",
            )

            for subset_content in subset_contents:
                new_tr = table_row(
                    variable=subset_content["short_name"],
                    title=subset_content["title"],
                    period=subset_content["period"],
                    compr=subset_content["compression_ratio"],
                    ssim=subset_content["ssim"],
                    mre=subset_content["mre"],
                )
                ov_table += new_tr

            ov_table += "</table>"
        return IPython.display.HTML(ov_table)

    except KeyError:
        raise ConnectionError("Stream not found")


def table_row(
    variable: str,
    title: str,
    period: str,
    compr: str,
    ssim: str,
    mre: str,
    st_st: str = "",
    st_en: str = "",
):
    tr = "<tr>"
    tr += f'<td style="text-align:left;">{st_st}{variable}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{title}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{period}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{compr}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{ssim}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{mre}{st_en}</td>'
    tr += "</tr>"
    return tr
