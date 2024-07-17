import numpy as np
from datetime import datetime
import requests
from requests import auth
import json
import subprocess as sp
import gc
import psutil

resolutions = ['stream_2k', 'stream_4k', 'stream_full']
ENDPOINT = 'https://dev.destinestreamer.geoville.com/api/streaming/metadata'
DATA_API = '/data/{short_name}/{start_date}/{end_date}'

API_DT_FORMAT = '%Y%m%dT%H%M'
FPS = 25


class BearerAuth(auth.AuthBase):

    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


class DTEStreamer:

    def __init__(self,
                 category_name: str,
                 short_name: str,
                 start_date: datetime,
                 end_date: datetime,
                 token_loc: str):

        self.category_name: str = category_name
        self.__short_name: str = short_name
        self.start_date: datetime = start_date
        self.end_date: datetime = end_date
        self.image_gen = None
        self.stream_metadata: dict = dict()
        self.frames_metadata: dict = dict()
        self.frame_count: int = -1
        self.start_frame: int = -1

        self.token = self.__extract_token(token_loc)

        self.__get_stream_and_metadata()

    @staticmethod
    def __extract_token(token_path: str):
        """
        This method extracts the HTTPS Bearer Token from the file specified in
        token_path. It is used to communicate
        with the DTE API.

        :param token_path:
        :type token_path: str

        :return token - (str):
        """
        token_path = token_path[token_path.find('/'):]
        f = open(token_path)

        token_json = f.readline()
        f.close()

        token = json.loads(token_json)['user_key']
        return token

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

            url = ENDPOINT + \
                DATA_API.format(short_name=self.__short_name,
                                start_date=api_start_date,
                                end_date=api_end_date)

            response = requests.get(url=url, auth=BearerAuth(self.token))
            content = json.loads(response.content)

            if response.status_code != 200:
                raise Exception(content)

            # saving the uri of the stream according to the selected resolution.
            self.stream_metadata = \
                {key: value for key, value in content.items() if key != 'images'}

            # saving metadata about the images:
            # date and time of image
            # min value for scale
            # max value for scale
            # frame number
            self.frames_metadata = json.loads(response.content)['images']

        except KeyError as e:
            raise ConnectionError('Stream not found')

        if (self.stream_metadata is None or
                len(self.stream_metadata) == 0
                or self.frames_metadata is None):
            raise SystemExit('Stream not found')

        self.frame_count = len(self.frames_metadata)
        self.start_frame = self.frames_metadata[0]['img_number'] - 1

    @staticmethod
    def __check_stderr(stderr_stream):
        """
        This method checks stderr of the ffmpeg read attempt for 403.
        If it's in the stream, a ConnectionError is thrown.
        Else it returns without value.

        :param stderr_stream:

        :return None:
        """

        stderr_content = stderr_stream.read()
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

        # if err.find('200') == -1:
        #     raise ConnectionError(f"Can't open stream: {err}", err)
        # else:
        #     return
        if err.find('403') != -1:
            raise ConnectionError(f"Can't open stream: 403 Access denied")
        else:
            return

    def images(self):
        """
        This function initializes an image generator for load_images.
        For this it accesses the stream, seeks to the time of the start_frame
        and sets -t to the duration needed to load as many frames as
        frame_count.

        :return: - load_images_non_rgb() or load_images_rgb() (generator)
        """
        command = ['ffmpeg', '-hide_banner',
                   '-ss', f'{self.start_frame / FPS:.2f}',
                   '-i', self.stream_metadata['stream_path'],
                   '-f', 'rawvideo',
                   '-t', f'{self.frame_count / FPS:.2f}',
                   'pipe:1']

        command.insert(6, '-pix_fmt')
        command.insert(7, 'grayf32le')

        process = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE)

        self.__check_stderr(process.stderr)
        self.image_gen = self.__load_images(process.stdout)

        return self.image_gen

    @staticmethod
    def __check_mem():
        """
        This static method checks virtual memory and returns a bool to indicate
        whether memory usage is ok. This is intended to reduce notebook crashes
        from loading too much data.

        :return: - is_mem_ok (bool)
        """
        if psutil.virtual_memory().percent >= 90:
            return False
        else:
            return True

    def __load_images(self, stdout):
        """
        This generator reads one frame from a stream on each __next__() call
        (i.e. every iteration in a for loop) and converts it into a numpy array.

        :param stdout:

        :return: - next_image (generator object)
        """

        expected_bands = 1
        creating_bands = 1
        pix_dtype = np.float32  # float16
        bytes_per_pixel_per_band = np.dtype(pix_dtype).itemsize
        cur_frame_number = 0

        expected_image_size = self.nx() * self.ny() * \
                              bytes_per_pixel_per_band * \
                              expected_bands

        created_image_size = self.nx() * self.ny() * \
                              bytes_per_pixel_per_band * \
                              creating_bands

        while True:
            buffer = stdout.read(expected_image_size)
            buffer = buffer[::expected_bands]

            if len(buffer) != created_image_size:
                if cur_frame_number == 0:
                    print('Empty stream, no data found.')
                break

            min_val = self.frames_metadata[cur_frame_number]['img_min_value']
            max_val = self.frames_metadata[cur_frame_number]['img_max_value']

            next_image = np.frombuffer(buffer, pix_dtype)
            next_image = self.__rescale_image(next_image, min_val, max_val)

            next_image = next_image.reshape(self.ny(), self.nx())
            next_image = np.flip(next_image, 0)

            del buffer
            gc.collect()

            yield next_image, datetime.strptime(
                self.frames_metadata[cur_frame_number]['img_date'],
                '%Y-%m-%dT%H:%M:%S')

            if not self.__check_mem():
                print('Memory usage too high. Exiting loop.')
                print('Already loaded data is still available.')
                break

            cur_frame_number += 1

        stdout.close()

    @staticmethod
    def __rescale_image(image: np.ndarray,
                        img_min_value: float,
                        img_max_value: float):
        """
        This static method rescales and ndarray to min and max values.
        :param image:
        :type image: np.ndarray
        :param img_min_value:
        :type img_min_value: float
        :param img_max_value:
        :type img_max_value: float

        :return: - rescaled_image (nd.array)
        """
        difference = np.subtract(img_max_value, img_min_value)
        product = np.multiply(image, difference)
        sum = np.add(product, img_min_value)
        return sum

    def unit(self):
        """
        This method returns the unit of the data represented in the stream.

        :return: - unit (str)
        """
        return self.stream_metadata['unit']

    def name(self):
        """
        This method returns the name of the data represented in the stream.

        :return: - name (str)
        """
        return self.stream_metadata['parameter_name']

    def short_name(self):
        """
        This method returns an abbreviated name of the data represented in the
        stream.

        :return: - short_name (str)
        """
        return self.stream_metadata['parameter_short_name']

    def type_of_level(self):
        """
        This method returns the type of level of the data represented in the
        stream.

        :return: - type_of_level (str)
        """
        return self.stream_metadata['type_of_level']

    def nx(self):
        """
        This method returns number of datapoints in x dimension.

        :return: - nx (int)
        """
        return self.stream_metadata['nx']

    def ny(self):
        """
        This method returns number of datapoints in y dimension.

        :return: - ny (int)
        """
        return self.stream_metadata['ny']

    def create_lon_lat_grid(self):
        """
        This method creates a numpy meshgrid with longitudes and latitudes for
        the represented data. The grid is intended to be used to create the
        xarray.DataArray.

        :return: - lon, lat (ndarray, ndarray)
        """
        return np.meshgrid(np.linspace(start=0, stop=359.75, num=self.nx()),
                           np.linspace(start=-90, stop=90, num=self.ny()))
