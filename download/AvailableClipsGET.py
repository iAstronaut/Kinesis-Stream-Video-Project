import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import jsonschema
from datetime import datetime

import ims_logger
import ims_authen
from ims_authen import USER_ROLE
from ims_utils.validator import IMS_Validator
from ims_utils.camera import get_available_clips
from ims_db.camera_db import get_camera
from ims_db.gateway_db import get_gateway

view_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"},
        "startTime": {"type": "string", "check_integer": {}},
        "duration": {"type": "string", "check_integer": {"min": 1, "max": 360}}
    },
    "required": ["cameraId", "startTime", "duration"]
}


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


def main_process(event, user_data):
    try:

        params = event.get("queryStringParameters")
        if params is None:
            params = {}
        jsonschema.validate(params, view_schema, IMS_Validator, IMS_Validator.FORMAT_CHECKER)
        camera_id = params.get("cameraId")
        start_time_stamp = int(params.get("startTime"))
        start_time = datetime.fromtimestamp(start_time_stamp)
        duration = int(params.get("duration"))
        item = get_camera(camera_id)
        if item is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")
        company_id = user_data.get("companyId")
        gateway = get_gateway(item.get("gatewayId"))
        if user_data.get("role") == USER_ROLE and company_id != gateway.get("companyId"):
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")

        list_clips = get_available_clips(camera_id, start_time, duration)
        return get_success_response(HTTPStatus.OK.value, list_clips)
    except jsonschema.exceptions.ValidationError as validate_err:
        message = str(validate_err.message)
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", message)
    except Exception as e:
        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
