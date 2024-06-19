from timeit import default_timer
from http import HTTPStatus
from jsonschema import exceptions, validate

from ims_utils.common import get_error_response, get_success_response
from ims_logger import logging
from ims_authen import FAIL_AUTHEN_RESPONSE, authenticate
from ims_db.camera_db import get_camera
from ims_utils.camera import BASIC_CAMERA_ATTRS, trim_attrs_camera

camera_get_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"}
    },
    "required": ["cameraId"]
}


def lambda_handler(event, context):
    start = default_timer()
    author = event["headers"].get("authorization")
    can_access, user_data = authenticate(author)
    if can_access:
        response = main_process(event, user_data)
    else:
        response = FAIL_AUTHEN_RESPONSE
    handling_time = int(1e3 * (default_timer() - start))
    logging(event, context, user_data, response, handling_time)
    return response


def main_process(event, user_data):
    try:
        params = event.get('queryStringParameters')
        validate(params, camera_get_schema)
        camera_id = params.get("cameraId")
        camera = get_camera(camera_id)

        if camera is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")

        camera = trim_attrs_camera(camera, BASIC_CAMERA_ATTRS)
        return get_success_response(HTTPStatus.OK.value, camera)
    except exceptions.ValidationError as validate_err:
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", str(validate_err.message))
    except Exception as e:

        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))