import time
import json
import jsonschema
import timeit
import uuid

import ims_authen
import ims_logger
from ims_utils.common import get_error_response, get_success_response
from ims_db.camera_db import get_camera, update_cam_preset
from ims_utils.gateway import add_preset, get_presets, NUM_CONTROL_RETRY
from ims_utils.validator import IMS_Validator
from http import HTTPStatus


camera_preset_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"},
        "name": {"type": "string"},
        "presetId": {"type": "string", "check_integer": {"min": 1, "max": 10}}
    },
    "required": ["cameraId", "presetId", "name"]
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
        data = json.loads(event.get("body"))
        jsonschema.validate(data, camera_preset_schema, IMS_Validator)
        camera_id = data.get("cameraId")
        preset_id = data.get("presetId")
        name = data.get("name")
        camera = get_camera(camera_id)
        if camera is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")
        unique_name = str(uuid.uuid4())[:8]

        add_preset(camera, int(preset_id), unique_name)
        added_preset = {"presetId": str(preset_id), "name": name}
        for i in range(NUM_CONTROL_RETRY):
            time.sleep(2)
            presets = get_presets(camera)
            if presets.get(str(preset_id)) and presets.get(str(preset_id)) == unique_name:
                update_cam_preset(camera_id, preset_id, name)
                return get_success_response(HTTPStatus.OK.value, added_preset)
        return get_error_response(HTTPStatus.REQUEST_TIMEOUT.value, "E021")
    except jsonschema.exceptions.ValidationError as validate_err:
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", str(validate_err.message))
    except Exception as e:
        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
