import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import tempfile
import subprocess
import os
import shutil

import jsonschema
from datetime import datetime

import ims_logger
import ims_authen
from ims_authen import USER_ROLE
from ims_utils.validator import IMS_Validator
from ims_utils.camera import save_clip_s3, get_video_clip, download_clip_from_s3, is_clip_exist_s3, generate_presigned_url
from ims_db.camera_db import get_camera
from ims_db.gateway_db import get_gateway

view_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"},
        "startTime": {"type": "string", "check_list_integer": {}},
        "endTime": {"type": "string", "check_list_integer": {}}
    },
    "required": ["cameraId", "startTime", "endTime"]
}

time_format = "%Y-%m-%d-%H:%M:%S"

def lambda_handler(event, context):
    start = timeit.default_timer()
    author = event["headers"].get("authorization")
    can_access, user_data = ims_authen.authenticate(author)
    if can_access:
        response = main_process(event, user_data)
    else:
        response = ims_authen.FAIL_AUTHEN_RESPONSE
    handling_time = int(1e3 * (timeit.default_timer() - start))
    ims_logger.logging(event, context, user_data, response, handling_time)
    return response

def download_clip_and_copy_to_tmp(camera_id, start_time_stamp, end_time_stamp, tmp_dir, data_file):
    start_time = datetime.fromtimestamp(start_time_stamp)
    end_time = datetime.fromtimestamp(end_time_stamp)
    item = get_camera(camera_id)
    video_clip = get_video_clip(camera_id, start_time, end_time)
    file_name = generate_file_name(item.get("cameraName"), start_time_stamp, end_time_stamp)
    object_key = "{}/{}".format(camera_id, file_name)
    save_clip_s3(object_key, file_name, video_clip["Payload"])
    file_tmp = "{}/{}".format(tmp_dir, file_name)
    download_clip_from_s3(object_key, file_tmp)
    with open(data_file, 'a') as f:
        f.write('file \'{}\'\n'.format(file_tmp))

def generate_file_name(cameraName, start_time_stamp, end_time_stamp):
    start_time = datetime.fromtimestamp(start_time_stamp)
    end_time = datetime.fromtimestamp(end_time_stamp)
    start_str = start_time.strftime(time_format)
    end_str = end_time.strftime(time_format)
    file_name = "{}-{}-{}.mp4".format(cameraName, start_str, end_str)
    return file_name

def main_process(event, user_data):
    try:
        params = event.get("queryStringParameters")
        if params is None:
            params = {}
        jsonschema.validate(params, view_schema, IMS_Validator, IMS_Validator.FORMAT_CHECKER)

        camera_id = params.get("cameraId")
        start_time_stamp = params.get("startTime")
        start_time_stamp_list = [int(x) for x in list(start_time_stamp.split(","))]
        end_time_stamp = params.get("endTime")
        end_time_stamp_list = [int(x) for x in list(end_time_stamp.split(","))]
        item = get_camera(camera_id)
        if item is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")

        company_id = user_data.get("companyId")
        gateway = get_gateway(item.get("gatewayId"))

        if user_data.get("role") == USER_ROLE and company_id != gateway.get("companyId"):
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")

        temp_dir_path = ""
        try:
            file_name = generate_file_name(item.get("cameraName"), start_time_stamp_list[0], end_time_stamp_list[-1])
            object_key = "{}/{}".format(camera_id, file_name)
            if is_clip_exist_s3(object_key):
                presigned_url = generate_presigned_url(object_key)
            else:
                temp_dir_path = tempfile.mkdtemp()
                data_file = os.path.join(temp_dir_path, "file_info.txt")
                output_path = os.path.join(temp_dir_path, "merged_file.mp4")
                for start_time, end_time in zip(start_time_stamp_list, end_time_stamp_list):
                    download_clip_and_copy_to_tmp(camera_id, start_time, end_time, temp_dir_path, data_file)

                ffmpeg_command = f"ffmpeg -f concat -safe 0 -i {data_file} -c copy {output_path} -metadata media_type='video'"
                subprocess.run(ffmpeg_command, shell=True)

                with open(output_path, 'rb') as data:
                    presigned_url = save_clip_s3(object_key, file_name, data)

                if os.path.exists(temp_dir_path):
                    shutil.rmtree(temp_dir_path)
            return get_success_response(HTTPStatus.OK.value, {"link": presigned_url})
        except:
            if os.path.exists(temp_dir_path):
                shutil.rmtree(temp_dir_path)
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E011")
    except jsonschema.exceptions.ValidationError as validate_err:
        message = str(validate_err.message)
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", message)
    except Exception as e:
        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
