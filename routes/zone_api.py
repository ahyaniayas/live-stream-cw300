import json

from flask import Blueprint, jsonify, request

import state
import database

bp = Blueprint("zones", __name__)


@bp.route("/zones", methods=["GET"])
def zones_list():
    with state._zones_lock:
        result = [
            {
                "id":            z["id"],
                "name":          z["name"],
                "points":        z["points"],
                "active":        z["active"],
                "total_count":   z["total_count"],
                "current_count": z["current_count"],
                "point_count":   len(z["points"]),
                "notify":        z.get("notify", False),
            }
            for z in state._zones.values()
        ]
    return jsonify(result)


@bp.route("/zones/<int:zone_id>/notify", methods=["POST"])
def zone_notify_toggle(zone_id):
    with state._zones_lock:
        if zone_id not in state._zones:
            return jsonify(error="zona tidak ditemukan"), 404
        state._zones[zone_id]["notify"] = not state._zones[zone_id].get("notify", False)
        s = state._zones[zone_id]["notify"]
    database.upsert_zone_notify(zone_id, s)
    return jsonify(ok=True, notify=s)


@bp.route("/zones", methods=["POST"])
def zone_create():
    data   = request.get_json(force=True, silent=True) or {}
    name   = (data.get("name") or "").strip()
    points = data.get("points", [])

    if not name:
        return jsonify(error="name wajib diisi"), 400
    if len(points) < 3:
        return jsonify(error="minimal 3 titik"), 400

    cleaned = []
    for p in points:
        x, y = float(p[0]), float(p[1])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return jsonify(error="koordinat harus 0.0–1.0"), 400
        cleaned.append([x, y])

    new_id = database.insert_zone(name, json.dumps(cleaned))
    with state._zones_lock:
        state._zones[new_id] = database.zone_runtime(new_id, name, cleaned)

    return jsonify(id=new_id, name=name, points=cleaned), 201


@bp.route("/zones/<int:zone_id>", methods=["PUT"])
def zone_update(zone_id):
    with state._zones_lock:
        if zone_id not in state._zones:
            return jsonify(error="zona tidak ditemukan"), 404

    data   = request.get_json(force=True, silent=True) or {}
    name   = (data.get("name") or "").strip() or None
    points = data.get("points")

    cleaned = None
    if points is not None:
        if len(points) < 3:
            return jsonify(error="minimal 3 titik"), 400
        cleaned = [[float(p[0]), float(p[1])] for p in points]

    database.update_zone(zone_id, name,
                         json.dumps(cleaned) if cleaned is not None else None)

    with state._zones_lock:
        if name:
            state._zones[zone_id]["name"] = name
        if cleaned is not None:
            state._zones[zone_id]["points"] = cleaned

    return jsonify(ok=True)


@bp.route("/zones/<int:zone_id>", methods=["DELETE"])
def zone_delete(zone_id):
    database.delete_zone(zone_id)
    with state._zones_lock:
        state._zones.pop(zone_id, None)
    return jsonify(ok=True)


@bp.route("/zones/<int:zone_id>/reset", methods=["POST"])
def zone_reset(zone_id):
    with state._zones_lock:
        if zone_id not in state._zones:
            return jsonify(error="zona tidak ditemukan"), 404
        state._zones[zone_id]["total_count"]   = 0
        state._zones[zone_id]["current_count"] = 0
        state._zones[zone_id]["active"]        = False
    database.upsert_zone_count(zone_id, 0)
    return jsonify(ok=True)
