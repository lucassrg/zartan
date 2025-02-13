import json
import logging
import logging.config

# import functions
from flask import render_template, url_for, redirect, session, request
from flask import Blueprint
from utils.okta import OktaAdmin, TokenUtil
from utils.udp import SESSION_INSTANCE_SETTINGS_KEY, get_app_vertical, get_udp_ns_fieldname, apply_remote_config
from utils.email import Email

from GlobalBehaviorandComponents.validation import is_authenticated, get_userinfo

logger = logging.getLogger(__name__)


# OKTA TENANT VARIABLES
# 1) Group Name for "Regular User"
# 2) Group Name for "Admin User"
# 3) Group Name startswith  for Agency Location
CONFIG_REGULAR = "USER"
CONFIG_ADMIN = "ADMIN"
CONFIG_LOCATION = "LOC"

# set blueprint
dealer_views_bp = Blueprint('dealer_views_bp', __name__, template_folder='templates', static_folder='static', static_url_path='static')


# dealer landing page
@dealer_views_bp.route("/profile")
@apply_remote_config
@is_authenticated
def dealer_profile_get():
    logger.debug("dealer_profile()")
    return render_template(
        "{0}/profile.html".format(get_app_vertical()),
        templatename=get_app_vertical(),
        id_token=TokenUtil.get_id_token(request.cookies),
        access_token=TokenUtil.get_access_token(request.cookies),
        user_info=get_userinfo(),
        config=session[SESSION_INSTANCE_SETTINGS_KEY],
        _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])

# dealer my applications
@dealer_views_bp.route("/myapps", methods=["GET"])
@apply_remote_config
@is_authenticated
def dealer_myapps_get():
    logger.debug("dealer_myapps_get()")

    CONFIG_GROUP_LOCATION_STARTSWITH = "{0}_".format(get_udp_ns_fieldname(CONFIG_LOCATION))

    user_info = get_userinfo()
    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])
    user = okta_admin.get_user(user_info["sub"])
    user_id = user["id"]

    location = ""

    # Find the groups the user belongs to and find the description of the _LOC_* group
    get_user_groups_response = okta_admin.get_user_groups(user_id=user_id)
    for item in get_user_groups_response:
        if item["profile"]["name"].startswith(CONFIG_GROUP_LOCATION_STARTSWITH):
            location = item["profile"]["description"]

    get_apps_response = okta_admin.get_applications_by_user_id(user_id)

    return render_template(
        "{0}/myapps.html".format(get_app_vertical()),
        templatename=get_app_vertical(),
        user_info=user_info,
        config=session[SESSION_INSTANCE_SETTINGS_KEY],
        location=location,
        apps=get_apps_response,
        _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])


@dealer_views_bp.route("/registration", methods=["GET"])
@apply_remote_config
def dealer_registration_get():
    logger.debug("dealer_registration()")
    CONFIG_GROUP_REGULAR = get_udp_ns_fieldname(CONFIG_REGULAR)
    CONFIG_GROUP_ADMIN = get_udp_ns_fieldname(CONFIG_ADMIN)
    CONFIG_GROUP_LOCATION_STARTSWITH = get_udp_ns_fieldname(CONFIG_LOCATION)

    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])

    setup_options = {
        "type_users": [],
        "dealerships": [],
        "type_user_selected": request.form.get('role'),
        "dealership_selected": request.form.get('location')
    }

    user_data = {
        "profile": {
            "firstName": "",
            "lastName": "",
            "email": "",
            "login": "",
            "mobilePhone": ""
        }
    }
    try:

        # Prepopulate choice for setup
        # Get Group
        group_get_response = okta_admin.get_groups_by_name(CONFIG_GROUP_ADMIN)
        for i in group_get_response:
            setup_options["type_users"].append({"id": i["id"], "description": i["profile"]["description"]})

        group_get_response = okta_admin.get_groups_by_name(CONFIG_GROUP_REGULAR)
        for i in group_get_response:
            setup_options["type_users"].append({"id": i["id"], "description": i["profile"]["description"]})

        group_get_response = okta_admin.get_groups_by_name(CONFIG_GROUP_LOCATION_STARTSWITH)
        for i in group_get_response:
            setup_options["dealerships"].append({"id": i["id"], "description": i["profile"]["description"]})

        # On a GET display the registration page with the defaults
        return render_template(
            "{0}/registration.html".format(get_app_vertical()),
            templatename=get_app_vertical(),
            config=session[SESSION_INSTANCE_SETTINGS_KEY],
            user_data=user_data,
            setup_options=setup_options,
            _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])
    except Exception as e:
        return render_template(
            "{0}/registration.html".format(get_app_vertical()),
            templatename=get_app_vertical(),
            config=session[SESSION_INSTANCE_SETTINGS_KEY],
            error=e,
            user_data=user_data,
            setup_options=setup_options,
            _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])


@dealer_views_bp.route("/registration", methods=["POST"])
@apply_remote_config
def dealer_registration_post():
    logger.debug("dealer_registration()")
    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])

    setup_options = {
        "type_users": [],
        "dealerships": [],
        "type_user_selected": request.form.get('role'),
        "dealership_selected": request.form.get('location')
    }

    # Prepopulate
    user_data = {
        "profile": {
            "firstName": request.form.get('firstname'),
            "lastName": request.form.get('lastname'),
            "email": request.form.get('email'),
            "login": request.form.get('email'),
            "mobilePhone": request.form.get('phonenumber'),
            get_udp_ns_fieldname("access_requests"): ['{id}'.format(id=request.form.get('location'))]
        },
        "credentials": {
            "password": {"value": request.form.get('password')}
        },
        "groupIds": []
    }

    user_data["groupIds"].append(setup_options["type_user_selected"])
    user_create_response = okta_admin.create_user(user_data, activate_user=False)

    if "errorCode" in user_create_response:

        CONFIG_GROUP_REGULAR = get_udp_ns_fieldname(CONFIG_REGULAR)
        CONFIG_GROUP_ADMIN = get_udp_ns_fieldname(CONFIG_ADMIN)
        CONFIG_GROUP_LOCATION_STARTSWITH = get_udp_ns_fieldname(CONFIG_LOCATION)

        # Prepopulate choice for setup
        # Get Group
        group_get_response = okta_admin.get_groups_by_name(CONFIG_GROUP_ADMIN)
        for i in group_get_response:
            setup_options["type_users"].append({"id": i["id"], "description": i["profile"]["description"]})

        group_get_response = okta_admin.get_groups_by_name(CONFIG_GROUP_REGULAR)
        for i in group_get_response:
            setup_options["type_users"].append({"id": i["id"], "description": i["profile"]["description"]})

        group_get_response = okta_admin.get_groups_by_name(CONFIG_GROUP_LOCATION_STARTSWITH)
        for i in group_get_response:
            setup_options["dealerships"].append({"id": i["id"], "description": i["profile"]["description"]})

        return render_template(
            "{0}/registration.html".format(get_app_vertical()),
            templatename=get_app_vertical(),
            config=session[SESSION_INSTANCE_SETTINGS_KEY],
            error=user_create_response,
            user_data=user_data,
            setup_options=setup_options)

    # Send Activation Email to the user
    EmailServices().emailRegistration(
        recipient={"address": request.form.get('email')},
        token=user_create_response["id"])

    return render_template(
        "{0}/registration-completion.html".format(get_app_vertical()),
        templatename=get_app_vertical(),
        config=session[SESSION_INSTANCE_SETTINGS_KEY],
        email=request.form.get('email'),
        _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])


@dealer_views_bp.route("/registration-state/<stateToken>", methods=["GET"])
@apply_remote_config
def dealer_registration_state_get(stateToken):
    logger.debug("dealer_registration_state_get()")
    user_id = stateToken
    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])
    user_activate_response = okta_admin.activate_user(user_id, send_email=False)
    if "errorCode" in user_activate_response:
        return render_template(
            "{0}/registration-state.html".format(get_app_vertical()),
            templatename=get_app_vertical(), config=session[SESSION_INSTANCE_SETTINGS_KEY],
            error=user_activate_response)

    return render_template(
        "{0}/registration-state.html".format(get_app_vertical()),
        templatename=get_app_vertical(),
        config=session[SESSION_INSTANCE_SETTINGS_KEY], _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])


@dealer_views_bp.route("/registration-completion", methods=["GET"])
@apply_remote_config
def dealer_registration_completion_get():
    logger.debug("dealer_registration_completion()")
    return render_template(
        "{0}/registration-completion.html".format(get_app_vertical()),
        templatename=get_app_vertical(),
        config=session[SESSION_INSTANCE_SETTINGS_KEY],
        _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])


@dealer_views_bp.route("/workflow-approvals", methods=["GET"])
@apply_remote_config
@is_authenticated
def workflow_approvals_get():
    logger.debug("workflow_approvals()")
    CONFIG_GROUP_ADMIN = get_udp_ns_fieldname(CONFIG_ADMIN)

    workflow_list = []
    user_info = get_userinfo()
    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])
    user = okta_admin.get_user(user_info["sub"])
    user_id = user["id"]

    # On a GET display the registration page with the defaults
    admin_groups = okta_admin.get_user_groups(user_id)
    admin_group_id = ""

    # Must be an admin
    for item in admin_groups:
        if item["profile"]["name"] == CONFIG_GROUP_ADMIN:
            admin_group_id = item["id"]

    if admin_group_id:
        # access_requests attribute contains workflow request
        # 'profile.access_requests  eq pr"

        # logger.debug("get_udp_ns_fieldname(access_requests):{0}".format(get_udp_ns_fieldname("access_requests")))

        user_get_response = okta_admin.get_user_list_by_search(
            'profile.{0} pr'.format(get_udp_ns_fieldname("access_requests")))
        for list in user_get_response:
            logger.debug("list_in_user_get_response():{0}".format(list))
            for grp in list["profile"][get_udp_ns_fieldname("access_requests")]:
                
                group_get_response = okta_admin.get_group(id=grp)
                logger.debug("group_get_response():{0}".format(json.dumps(group_get_response)))
                logger.debug("group_get_response[...]():{0}".format(json.dumps(group_get_response["profile"]["description"])))
                var = {
                    "requestor": list["profile"]["login"],
                    "request": group_get_response["profile"]["description"],
                    "usr_grp": {"user_id": list["id"], "group_id": grp}
                }
                workflow_list.append(var)

        return render_template(
            "{0}/workflow-approvals.html".format(get_app_vertical()),
            templatename=get_app_vertical(),
            workflow_list=workflow_list,
            user_info=user_info,
            config=session[SESSION_INSTANCE_SETTINGS_KEY],
            _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])
    else:
        return "ERROR: Unauthorized", 401


@dealer_views_bp.route("/workflow-approvals", methods=["POST"])
@apply_remote_config
@is_authenticated
def workflow_approvals_post():
    logger.debug("workflow_approvals_post()")
    user_info = get_userinfo()
    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])
    user = okta_admin.get_user(user_info["sub"])
    user_id = user["id"]
    
    logger.debug("workflow_approvals():{0}",request.form)

    if request.form.get("action") == "reject":
        req = request.form.get("action_value")
        req = req.replace("\'", "\"")
        req = json.loads(req)
        user_id = req["user_id"]
        group_id = req["group_id"]
        user_wf = okta_admin.get_user(user_id)

        grps = user_wf["profile"][get_udp_ns_fieldname("access_requests")]
        grps.remove(group_id)

        # Remove user attribute organization ( as the request has been rejected)
        user_data = {
            "profile": {
                get_udp_ns_fieldname("access_requests"): grps
            }
        }
        okta_admin.update_user(user_id=user_id, user=user_data)

    if request.form.get("action") == "approve":
        req = request.form.get("action_value")

        logger.debug("workflow_approvals():approve:request:{0}",req) 

        req = req.replace("\'", "\"")
        req = json.loads(req)

        
        user_id = req["user_id"]
        group_id = req["group_id"]
        logger.debug("workflow_approvals():approve:request:user_id{0}",user_id) 
        logger.debug("workflow_approvals():approve:request:group_id{0}",group_id) 

        # Assign user to group
        okta_admin.assign_user_to_group(group_id, user_id)

        user_wf = okta_admin.get_user(user_id)

        grps = user_wf["profile"][get_udp_ns_fieldname("access_requests")]
        grps.remove(group_id)

        # Remove user attribute organization ( as the request has been rejected)
        user_data = {
            "profile": {
                get_udp_ns_fieldname("access_requests"): grps,
                "department": "Sales"
            }
        }
        okta_admin.update_user(user_id=user_id, user=user_data)

        user_activate_response = okta_admin.activate_user(user_id, send_email=True)
        if "errorCode" in user_activate_response:
            logger.debug("workflow_approvals_post():failed to activate user:{0}",user_activate_response)


    return redirect(url_for("dealer_views_bp.workflow_approvals_get", _external=True, _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"]))


@dealer_views_bp.route("/workflow-requests", methods=["GET"])
@apply_remote_config
@is_authenticated
def workflow_requests_get():
    logger.debug("workflow_requests_get()")
    CONFIG_GROUP_LOCATION_STARTSWITH = get_udp_ns_fieldname(CONFIG_LOCATION)

    user_info = get_userinfo()
    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])
    user = okta_admin.get_user(user_info["sub"])
    user_id = user["id"]
    if get_udp_ns_fieldname("access_requests") in user["profile"]:
        pendingRequest = user["profile"][get_udp_ns_fieldname("access_requests")]
    else:
        pendingRequest = []

    workflow_list = []

    # On a GET display the registration page with the defaults
    list_group_user = []
    list_group_full = []

    is_user_dealership = False

    # Find the groups the user belongs to
    get_user_groups_response = okta_admin.get_user_groups(user_id=user_id)
    for item in get_user_groups_response:
        if item["profile"]["name"].startswith(CONFIG_GROUP_LOCATION_STARTSWITH):
            is_user_dealership = True

        if item["profile"]["name"] != "Everyone":  # Ignore the Everyone group
            group_id = "{id}".format(id=item["id"])
            list_group_user.append({"id": item["id"],
                                    "name": item["profile"]["name"],
                                    "description": item["profile"]["description"],
                                    "status": "Pending" if group_id in pendingRequest else "Not Requested"})
    # If not a user of a dealership, cannot request access to applications
    if is_user_dealership:
        # Find the groups for this portal that start with name "DEALER_"
        get_groups = okta_admin.get_groups_by_name(get_udp_ns_fieldname(""))
        for item in get_groups:
            group_id = "{id}".format(id=item["id"])
            list_group_full.append({"id": item["id"],
                                    "name": item["profile"]["name"],
                                    "description": item["profile"]["description"],
                                    "status": "Pending" if group_id in pendingRequest else "Not Requested"})

        # Populate the workflow list with groups that the user is absent in
        set_list1 = set(tuple(sorted(d.items())) for d in list_group_full)
        set_list2 = set(tuple(sorted(d.items())) for d in list_group_user)
        set_difference = set_list1 - set_list2
        for tuple_element in set_difference:
            workflow_list.append(dict((x, y) for x, y in tuple_element))

        return render_template(
            "{0}/workflow-requests.html".format(get_app_vertical()),
            templatename=get_app_vertical(),
            user_info=user_info,
            workflow_list=workflow_list,
            config=session[SESSION_INSTANCE_SETTINGS_KEY],
            _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])
    else:  # If not a user of a dealership, cannot request access to applications
        return render_template(
            "{0}/workflow-requests.html".format(get_app_vertical()),
            templatename=get_app_vertical(),
            user_info=user_info,
            error="You have not been assigned to a dealership. Only users of a dealership can request access to applications",
            config=session[SESSION_INSTANCE_SETTINGS_KEY],
            _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])


@dealer_views_bp.route("/workflow-requests", methods=["POST"])
@apply_remote_config
@is_authenticated
def workflow_requests_post():
    logger.debug("workflow_requests_post()")
    user_info = get_userinfo()
    okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])
    user = okta_admin.get_user(user_info["sub"])
    user_id = user["id"]
    if get_udp_ns_fieldname("access_requests") in user["profile"]:
        pendingRequest = user["profile"][get_udp_ns_fieldname("access_requests")]
    else:
        pendingRequest = []

    if request.form.get("request_access"):
        group_id = request.form.get("request_access")

        pendingRequest.append(group_id)

        # Remove user attribute organization ( as the request has been rejected)
        # organization": "[ '{id}' ]".format(id=request.form.get('location'))
        user_data = {
            "profile": {
                get_udp_ns_fieldname("access_requests"): pendingRequest
            }
        }
        okta_admin.update_user(user_id=user_id, user=user_data)
        EmailServices().emailWorkFlowRequest()

    return redirect(url_for("dealer_views_bp.workflow_requests_get", _external=True, _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"]))


# Class containing email services and formats
class EmailServices:

    # Email all members that belong to the group such as the Admin
    def emailAllMembersOfGroup(self, group_name, subject, message):
        logger.debug("emailAllMembersOfGroup()")
        okta_admin = OktaAdmin(session[SESSION_INSTANCE_SETTINGS_KEY])

        # Find the Admin Group
        group_list = okta_admin.get_groups_by_name(group_name)
        for group in group_list:
            if group["profile"]["name"] == group_name:
                group_id = group["id"]

        # Find All members that will be notified
        recipients = []
        user_list = okta_admin.get_user_list_by_group_id(group_id)
        for user in user_list:
            recipients.append({"address": user["profile"]["email"]})

        if recipients:
            email_send = Email.send_mail(subject=subject, message=message, recipients=recipients)
            return email_send

    # EMail workflow Request to the Admin
    def emailWorkFlowRequest(self):
        logger.debug("emailWorkFlowRequest()")

        CONFIG_GROUP_ADMIN = get_udp_ns_fieldname(CONFIG_ADMIN)
        activation_link = url_for("dealer_views_bp.workflow_approvals_get", _external=True, _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])
        # Send Activation Email to the Admin
        subject_admin = "A workflow request was received"
        message_admin = """
            A new request for access was received. The request is awaiting your approval.
            Click this link to log into your account <br />
            <a href='{activation_link}'>{activation_link}</a> to review the request"
            """.format(activation_link=activation_link)
        return self.emailAllMembersOfGroup(group_name=CONFIG_GROUP_ADMIN, subject=subject_admin, message=message_admin)

    # Email user and admin when a new user registers successfully
    def emailRegistration(self, recipient, token):
        logger.debug("emailRegistration()")
        CONFIG_GROUP_ADMIN = get_udp_ns_fieldname(CONFIG_ADMIN)

        app_title = session[SESSION_INSTANCE_SETTINGS_KEY]["settings"]["app_name"]
        activation_link = url_for(
            "dealer_views_bp.dealer_registration_state_get",
            stateToken=token,
            _external=True,
            _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"])
        subject = "Welcome to the {app_title}".format(app_title=session[SESSION_INSTANCE_SETTINGS_KEY]["settings"]["app_name"])
        # Send Activation Email to the user
        message = """
            Welcome to the {app_title}! Click this link to activate your account <br />
            <a href='{activation_link}'>{activation_link}</a>).
            """.format(app_title=app_title, activation_link=activation_link)
        Email.send_mail(subject=subject, message=message, recipients=[recipient])

        # Send Activation Email to the Admin
        subject_admin = "Registration Activation request for user {user}".format(user=request.form.get('email'))
        message_admin = """
            A new user has registered. His request is awaiting your approval.
            Click this link to log into your account <br />
            <a href='{activation_link}'>{activation_link}</a> to review the request
            """.format(
            activation_link=url_for(
                "dealer_views_bp.workflow_approvals_get",
                _external=True,
                _scheme=session[SESSION_INSTANCE_SETTINGS_KEY]["app_scheme"]))

        return self.emailAllMembersOfGroup(group_name=CONFIG_GROUP_ADMIN, subject=subject_admin, message=message_admin)
