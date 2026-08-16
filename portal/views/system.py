"""Storage: how full the drives are and whether any of them is dying."""
from flask import Blueprint, render_template
from flask_login import login_required

from ..services import disks as disk_service

bp = Blueprint("system", __name__, url_prefix="/system")


@bp.route("/disks")
@login_required
def disks():
    return render_template("system/disks.html", report=disk_service.summary())
