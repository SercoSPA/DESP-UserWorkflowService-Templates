from typing import Generator, Tuple
import numpy as np
from datetime import datetime
import requests
from requests import auth
import json
import subprocess as sp
from numba import njit
import IPython
import time

API = 'https://streamer.destine.eu/api/streaming/data/'
STREAM_EP = 'metadata/{category_name}/{short_name}/{start_date}/{end_date}'
OV_EP = 'overview/'

API_DT_FORMAT = '%Y%m%dT%H%M'
FPS = 25


class BearerAuth(auth.AuthBase):

    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


@njit(parallel=True)
def make_image(buffer: bytes, img_min_value: float, img_max_value: float, ny: int, nx: int):
    image = np.frombuffer(buffer, np.uint16) / 4095.0
    image = (image*(img_max_value-img_min_value) + img_min_value)
    image = image.reshape(ny, nx)
    return image


class DTEStreamer:

    def __init__(self,
                 category_name: str,
                 short_name: str,
                 start_date: datetime,
                 end_date: datetime,

                 token: str):

        self.category_name: str = category_name
        self.__short_name: str = short_name
        self.start_date: datetime = start_date
        self.end_date: datetime = end_date
        self.__stream_metadata: dict = dict()
        self.__frames_metadata: dict = dict()
        self.__frame_count: int = -1
        self.__start_img_number: int = -1
        self.__stdout = None
        self.__process = None
        self.__cur_frame_number = -1

        self.token = token

        timestamp = time.time()
        self.__get_stream_and_metadata()
        self.__bufsize = int(self.nx() * self.ny() * 2)
        # seek to first data frame in the selected time span

        timestamp = time.time()
        self.__seek_to_frame(self.__frames_metadata[0]['img_number']-1)

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

            url = API + \
                STREAM_EP.format(category_name=self.category_name,
                                 short_name=self.__short_name,
                                 start_date=api_start_date,
                                 end_date=api_end_date)
            response = requests.get(url=url, auth=BearerAuth(self.token))

            if response.status_code != 200:
                print(f"API error {response.status_code}: {response.content.decode('utf-8')}")
                raise SystemExit

            content = json.loads(response.content)

            # saving the uri of the stream according to the selected resolution.
            self.__stream_metadata = \
                {key: value for key, value in content.items() if key != 'images'}

            # saving metadata about the images:
            # date and time of image
            # min value for scale
            # max value for scale
            # frame number
            self.__frames_metadata = json.loads(response.content)['images']

        except KeyError:
            raise ConnectionError('Stream not found')

        if (self.__stream_metadata is None or
                len(self.__stream_metadata) == 0
                or self.__frames_metadata is None):
            print('No data found')
            raise SystemExit

        self.__frame_count = len(self.__frames_metadata)
        self.__start_img_number = self.__frames_metadata[0]['img_number']

    @staticmethod
    def __check_stderr(stderr_stream):
        """
        This method checks stderr of the ffmpeg read attempt for 403.
        If it's in the stream, a ConnectionError is thrown.
        Else it returns without value.

        :param stderr_stream:

        :return None:
        """

        stderr_content = stderr_stream.read(1000)
        stderr_stream.close()

        if stderr_content is None:
            return

        err = stderr_content.decode('utf-8')
        start_pos = err.find(']') + 1

        if start_pos == -1:
            return

        err = err[start_pos:].lstrip(' ')
        end_pos = err.find('\n')

        err = err[:end_pos].rstrip('\n')

        if err.find('403') != -1:
            raise ConnectionError("Can't open stream: 403 Access denied")
        else:
            return

    def seek_to_date(self, date: datetime):
        """
        Binary Search Algorithm to find the frame that is at the specified time. If the exact date and time is
        not available, the one closest but prior to it will be used.
        """
        min_pos = 0
        max_pos = len(self.__frames_metadata)-1
        chk_pos = int((min_pos+max_pos)/2)

        # Is date in range?
        min_date = self.__frames_metadata[0]['img_date']
        min_date = datetime.strptime(min_date, '%Y-%m-%dT%H:%M:%S')
        max_date = self.__frames_metadata[-1]['img_date']
        max_date = datetime.strptime(max_date, '%Y-%m-%dT%H:%M:%S')

        if not (min_date <= date <= max_date):
            # raise IndexError(f"date out of bounds: {date.strftime('%Y-%m-%dT%H:%M:%S')}")
            self.__kill_sp()
            return False

        # If the date to seek to is equal to the max date in the list, the algorithm will not find it. It will
        # always take the penultimate date. Therefore this check has to be in place
        if date == max_date:
            self.__seek_to_frame(max_pos + (self.__start_img_number - 1))
            return True

        while True:
            img_date = self.__frames_metadata[chk_pos]['img_date']
            img_date = datetime.strptime(img_date, '%Y-%m-%dT%H:%M:%S')

            if img_date > date:
                max_pos = chk_pos
                chk_pos = int((min_pos+max_pos)/2)
            elif img_date < date:
                min_pos = chk_pos
                chk_pos = int((min_pos+max_pos)/2)
            else:
                self.__seek_to_frame(chk_pos + (self.__start_img_number - 1))
                return True

            # Here, case min_pos and max_pos are neighbors and the date to seek to is not in the list.
            # In this case, take the closest previous date closest date provided, which is min_pos.
            if min_pos == chk_pos:
                img_date = self.__frames_metadata[chk_pos]['img_date']
                img_date = datetime.strptime(img_date, '%Y-%m-%dT%H:%M:%S')
                self.__seek_to_frame(chk_pos + (self.__start_img_number - 1))
                return True

    def __seek_to_frame(self, frame_number=0):

        if not self.__start_img_number-1 <= frame_number < (self.__start_img_number - 1) + self.__frame_count:
            raise IndexError(f'Frame number {frame_number} out of bounds [{self.__start_img_number}: ' +
                             f'{(self.__start_img_number - 1) + self.__frame_count-1}]')

        self.__cur_frame_number = frame_number

        command = ['ffmpeg', '-hide_banner',
                   '-ss', f'{self.__cur_frame_number / FPS:.2f}',
                   '-i', self.__stream_metadata['stream_path'],
                   # '-map', '0:v',
                   # '-c:v', 'copy',
                   # '-bsf:v', 'hevc_mp4toannexb',
                   # '-vsync', 'passthrough',
                   # '-framerate', '250'
                   # to doesnt work apparently
                   # '-to', f'{(self.__start_img_number - 1) + self.__frame_count / FPS:.2f}',
                   '-t', f'{(self.__frame_count-(self.__cur_frame_number - (self.__start_img_number - 1))) / FPS:.2f}',
                   '-f', 'rawvideo',
                   'pipe:1']

        self.__kill_sp()
        self.__process = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE, bufsize=self.__bufsize)

        self.__check_stderr(self.__process.stderr)

    def __kill_sp(self):
        if self.__stdout is not None:
            self.__stdout.close()

        if self.__process is not None:
            self.__process.kill()

    def load_next_image(self) -> Generator[Tuple[np.ndarray, datetime], None, None]:
        while True:
            if self.__process.stdout.closed:
                return

            buffer = self.__process.stdout.read(self.__bufsize)

            if len(buffer) != self.__bufsize:
                if self.__cur_frame_number == 0:
                    print('Empty stream, no data found.')
                return

            min_val = self.__cur_frame_metadata()['img_min_value']
            max_val = self.__cur_frame_metadata()['img_max_value']

            img_date = self.__cur_frame_metadata()['img_date']
            img_date = datetime.strptime(img_date, '%Y-%m-%dT%H:%M:%S')

            if np.isinf(min_val) or np.isinf(max_val):
                # create an image with inf values
                next_image = np.full((self.ny(), self.nx()), np.inf, np.float32)
            else:
                # create image from buffer
                next_image = make_image(buffer, min_val, max_val, self.ny(), self.nx())

            # set index for the next frame
            self.__cur_frame_number += 1

            yield next_image, img_date

    def __cur_frame_metadata(self):
        return self.__frames_metadata[self.__cur_frame_number-(self.__start_img_number-1)]

    def unit(self):
        """
        This method returns the unit of the data represented in the stream.

        :return: - unit (str)
        """
        return self.__stream_metadata['unit']

    def name(self):
        """
        This method returns the name of the data represented in the stream.

        :return: - name (str)
        """
        return self.__stream_metadata['parameter_name']

    def short_name(self):
        """
        This method returns an abbreviated name of the data represented in the
        stream.

        :return: - short_name (str)
        """
        return self.__stream_metadata['parameter_short_name']

    def type_of_level(self):
        """
        This method returns the type of level of the data represented in the
        stream.

        :return: - type_of_level (str)
        """
        return self.__stream_metadata['type_of_level']

    def nx(self):
        """
        This method returns number of datapoints in x dimension.

        :return: - nx (int)
        """
        return self.__stream_metadata['nx']

    def ny(self):
        """
        This method returns number of datapoints in y dimension.

        :return: - ny (int)
        """
        return self.__stream_metadata['ny']

    def create_lat_lon_grid(self):
        """
        This method creates a numpy meshgrid with longitudes and latitudes for
        the represented data. The grid is intended to be used to create the
        xarray.DataArray.

        :return: - lat, lon (ndarray, ndarray)
        """

        lon_start = self.__stream_metadata['lon_start']
        lon_end = self.__stream_metadata['lon_end']
        lat_start = self.__stream_metadata['lat_start']
        lat_end = self.__stream_metadata['lat_end']

        lon = np.linspace(start=lon_start, stop=lon_end, num=self.nx())
        lat = np.linspace(start=lat_start, stop=lat_end, num=self.ny())

        return lat, lon


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

        ov_table = ''

        for category_name, category_contents in response_content.items():
            ov_table += f'<h4>Category: <b>{category_name}</b></h4>'
            ov_table += '<table >'
            ov_table += table_row(short_name='short_name',
                                  title='title',
                                  period='period',
                                  compr='compression rate',
                                  ssim='SSIM',
                                  mre='mean relative error',
                                  st_st='<b style="align:left">',
                                  st_en='</b>')

            for category_content in category_contents:
                new_tr = table_row(short_name=category_content['short_name'],
                                   title=category_content['title'],
                                   period=category_content['period'],
                                   compr=category_content['compression_ratio'],
                                   ssim=category_content['ssim'],
                                   mre=category_content['mre'])
                ov_table += new_tr

            ov_table += '</table>'
        return IPython.display.HTML(ov_table)

    except KeyError:
        raise ConnectionError('Stream not found')


def table_row(short_name: str,
              title: str,
              period: str,
              compr: str,
              ssim: str,
              mre: str,
              st_st: str = '',
              st_en: str = ''):

    tr = '<tr>'
    tr += f'<td style="text-align:left;">{st_st}{short_name}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{title}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{period}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{compr}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{ssim}{st_en}</td>'
    tr += f'<td style="text-align:left;">{st_st}{mre}{st_en}</td>'
    tr += '</tr>'
    return tr
