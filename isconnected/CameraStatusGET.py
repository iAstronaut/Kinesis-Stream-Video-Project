import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import jsonschema

import ims_logger
import ims_authen
from ims_authen import USER_ROLE
from ims_utils.camera import get_camera_connectivity
from ims_db.camera_db import get_camera
from ims_db.gateway_db import get_gateway

camera_get_schema = {
    "type": "object",
    "properties": {
        "cameraId": {"type": "string"}
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
        params = event.get('queryStringParameters')
        jsonschema.validate(params, camera_get_schema)
        camera_id = params.get("cameraId")
        camera = get_camera(camera_id)
        company_id = user_data.get("companyId")
        if camera is None:
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")
        gateway = get_gateway(camera.get("gatewayId"))
        if user_data.get("role") == USER_ROLE and company_id != gateway.get("companyId"):
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E008")
        status = get_camera_connectivity(camera)
        return get_success_response(HTTPStatus.OK.value, {"status": status})
    except jsonschema.exceptions.ValidationError as validate_err:
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", str(validate_err.message))
    except Exception as e:

        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
