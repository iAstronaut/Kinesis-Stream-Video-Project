import jsonschema
import timeit

import ims_authen
import ims_logger
from ims_utils.common import get_error_response, get_success_response
from ims_db.camera_db import get_camera
from ims_utils.gateway import get_presets, transform_presets
from http import HTTPStatus


camera_preset_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"},
    },
    "required": ["cameraId"]

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
        jsonschema.validate(params, camera_preset_schema)
        camera_id = params.get("cameraId")
        camera = get_camera(camera_id)
        if camera is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")
        presets = get_presets(camera)
        data = transform_presets(camera, presets)
        return get_success_response(HTTPStatus.OK.value, data)
    except jsonschema.exceptions.ValidationError as validate_err:
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", str(validate_err.message))
    except Exception as e:
        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
