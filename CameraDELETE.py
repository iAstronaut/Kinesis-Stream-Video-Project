import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import ims_logger
import ims_authen
from ims_authen import ADMIN_ROLE
from ims_utils.camera import delete_camera_kinesis, trim_attrs_camera
from ims_utils.gateway import update_gw_cameras_shadow, delete_camera_thing
from ims_db.camera_db import get_camera, delete_camera

ACCEPT_ROLES = [ADMIN_ROLE]


def lambda_handler(event, context):
    start = timeit.default_timer()
    author = event["headers"].get("authorization")
    can_access, user_data = ims_authen.authenticate(author, ACCEPT_ROLES)
    if can_access:
        response = main_process(event, user_data)
    else:
        response = ims_authen.FAIL_AUTHEN_RESPONSE
    handling_time = int(1e3 * (timeit.default_timer() - start))
    ims_logger.logging(event, context, user_data, response, handling_time)
    return response


def main_process(event, user_data):
    try:
        camera_id = event['queryStringParameters'].get("cameraId")
        exist_camera = get_camera(camera_id)
        if exist_camera is None or exist_camera.get("isActive") != "True":
            return get_error_response(HTTPStatus.NOT_FOUND.value, "E007")
        delete_camera_kinesis(camera_id)
        delete_camera_thing(camera_id)
        delete_camera(camera_id)
        update_gw_cameras_shadow(exist_camera.get("gatewayId"), camera_id)
        exist_camera = trim_attrs_camera(exist_camera)
        return get_success_response(HTTPStatus.OK.value, exist_camera)
    except Exception as e:

        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
