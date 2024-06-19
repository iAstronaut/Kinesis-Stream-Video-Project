import jsonschema
import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import ims_logger
import ims_authen
from ims_authen import ADMIN_ROLE
from ims_utils.camera import get_snapshot, check_snapshot, take_snapshot
from ims_db.camera_db import get_camera
from ims_utils.validator import IMS_Validator

snapshot_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"},
        "interval": {"type": "string", "check_integer": {"min": 5, "max": 60}}

    },
    "required": ["cameraId", "interval"]
}
ACCEPT_ROLES = [ADMIN_ROLE]


def lambda_handler(event, context):
    start = timeit.default_timer()
    author = event["headers"].get("authorization")
    can_access, user_data = ims_authen.authenticate(author, ACCEPT_ROLES)
    if can_access:
        response = main_process(event, user_data)
    else:
        response = ims_authen.FAIL_AUTHEN_RESPONSE
    if response.get("statusCode") != HTTPStatus.OK.value:
        handling_time = int(1e3 * (timeit.default_timer() - start))
        ims_logger.logging(event, context, user_data, response, handling_time)
    return response


def main_process(event, user_data):
    try:
        params = event.get('queryStringParameters')
        if params is None:
            params = {}
        jsonschema.validate(params, snapshot_schema, IMS_Validator)
        camera_id = params.get("cameraId")
        interval = int(params.get("interval"))
        item = get_camera(camera_id)
        response = {"image": None, "snapshottime": None}
        if item is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")
        try:
            snapshot_time = check_snapshot(camera_id, interval)
            if snapshot_time is None:
                snapshot_time = take_snapshot(camera_id)
            if snapshot_time is not None:
                response["image"] = get_snapshot(camera_id)
                response["snapshottime"] = snapshot_time

        except:
            pass
        return get_success_response(HTTPStatus.OK.value, response)
    except jsonschema.exceptions.ValidationError as validate_err:

        message = str(validate_err.message)
        if validate_err.json_path == "$.interval":
            message = "interval must number from 5 to 60."
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", message)
    except Exception as e:
        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
