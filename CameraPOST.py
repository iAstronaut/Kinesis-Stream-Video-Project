import json
import timeit
from ims_utils.common import get_error_response, get_success_response
from http import HTTPStatus

import uuid
from datetime import datetime
import jsonschema

import ims_logger
import ims_authen
from ims_authen import ADMIN_ROLE
from ims_utils.gateway import update_gw_cameras_shadow, get_gateway_info,create_camera_thing, update_camera_shadow
from ims_utils.camera import create_camera_kinesis, trim_attrs_camera, is_duplicate_resource, \
    set_resource_settings, validate_camera_settings, get_cam_pre_status
from ims_db.camera_db import create_camera
from ims_db.gateway_db import get_gateway
from ims_db.model_db import get_model
from ims_utils.model import SETTINGS_SCHEMA

camera_add_schema = {
    "type": "object",
    "properties": {
        "cameraName": {"type": "string"},
        "gatewayId": {"type": "string"},
        "modelId": {"type": "string"},
        "resource": {"type": "string"},
        "description": {"type": "string"},
        "settings": SETTINGS_SCHEMA,
        "isEnable": {"type": "boolean"}
    },
    "required": ["cameraName", "gatewayId", "modelId", "isEnable"]
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
    handling_time = int(1e3 * (timeit.default_timer() - start))
    ims_logger.logging(event, context, user_data, response, handling_time)
    return response


def main_process(event, user_data):
    try:
        data = json.loads(event.get("body"))
        jsonschema.validate(data, camera_add_schema)
        name = data.get("cameraName")
        resource = data.get("resource")
        gateway_id = data.get("gatewayId")
        model_id = data.get("modelId")
        description = data.get("description") if data.get("description") else ""
        is_enable = data.get("isEnable")
        model = get_model(model_id)
        if not model:
            return get_error_response(HTTPStatus.NOT_FOUND, "E006")

        settings = model.get("settings")
        input_settings = data.get("settings") if data.get("settings") else {}
        settings.update(input_settings)
        set_resource_settings(settings, model.get("connectionType"), resource)
        validate_camera_settings(settings, model)
        gateway = get_gateway(gateway_id)
        _, gw_ip = get_gateway_info(gateway)
        if is_duplicate_resource(settings, gateway, gw_ip):
            return get_error_response(HTTPStatus.CONFLICT.value, "E013")
        company_id = gateway.get("companyId")
        status = get_cam_pre_status(gateway, model, is_enable)
        isPTZ = model.get("isPTZ") == True
        pipeline = model.get("pipeline")
        connectionType = model.get("connectionType")
        camera_id = str(uuid.uuid4())
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        camera = {"cameraId": camera_id,
                  "gatewayId": gateway_id,
                  "companyId": company_id,
                  "cameraName": name,
                  "searchName": name.lower(),
                  "resource": resource,
                  "description": description,
                  "modelId": model_id,
                  "settings": settings,
                  "isEnable": is_enable,
                  "isPTZ": isPTZ,
                  "pipeline": pipeline,
                  "connectionType": connectionType,
                  "createdBy": user_data.get("userId"),
                  "modifiedBy": user_data.get("userId"),
                  'createdTime': current_time,
                  "modifiedTime": current_time,
                  "status": status,
                  "isActive": "True"}
        added_camera = create_camera(camera)
        create_camera_kinesis(gateway_id, camera_id)
        update_gw_cameras_shadow(gateway_id, camera_id)
        create_camera_thing(gateway_id, camera_id)
        update_camera_shadow(added_camera)
        return get_success_response(HTTPStatus.CREATED.value, trim_attrs_camera(added_camera))
    except jsonschema.exceptions.ValidationError as validate_err:
        message = str(validate_err.message)
        if validate_err.json_path == "$.lowmode":
            message = "Camera model support this lowmode."
        return get_error_response(HTTPStatus.BAD_REQUEST.value, "E003", message)
    except Exception as e:

        return get_error_response(HTTPStatus.INTERNAL_SERVER_ERROR.value, "E001", str(e))
