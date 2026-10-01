from flask import Flask, request, jsonify
import logging
import os
from urllib.parse import unquote

from state_lookup import STATE_BY_ZIP5, MILITARY_PREFIX
from vamc_lookup import VAMC_LOOKUP
from county_lookup import AZ_COUNTY_LOOKUP

__API_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")

logging.basicConfig(level="DEBUG")

app = Flask(__name__)

logging.info(f"State lookup ready: {len(STATE_BY_ZIP5)} five-digit zips")
logging.info(f"VAMC lookup ready: {len(VAMC_LOOKUP)} entries")
logging.info(f"AZ county lookup ready: {len(AZ_COUNTY_LOOKUP)} entries")


def _clean_zipcode(zipcode):
    """Clean and normalize a zipcode string.

    Returns:
        tuple: (zip5, prefix) or (None, None) if invalid
    """
    if not zipcode:
        return None, None

    clean = unquote(str(zipcode)).strip().replace("-", "")

    if len(clean) < 3 or not clean[:3].isdigit():
        return None, None

    prefix = clean[:3]
    zip5 = clean[:5] if len(clean) >= 5 and clean[:5].isdigit() else None

    return zip5, prefix


def _nearest_match(prefix, lookup):
    """Find nearest mapped prefix by scanning outward numerically."""
    p = int(prefix)
    for offset in range(1, 100):
        for candidate in [str(p + offset).zfill(3), str(p - offset).zfill(3)]:
            if candidate in lookup:
                return lookup[candidate]
    return None


def lookup_vamc(prefix):
    """Look up presumptive VAMC from a 3-digit zip prefix."""
    result = VAMC_LOOKUP.get(prefix)
    if result:
        return result
    return _nearest_match(prefix, VAMC_LOOKUP)


def lookup_state(zip5):
    """Look up state from a full five-digit zipcode.

    The zip must be a real zip in the table; anything else (a short zip,
    a zip that lost its leading zero, an unknown zip) has no state. We never
    guess a state from the first three digits: a damaged zip like 2809
    (really 02809, Rhode Island) would read as prefix 280, North Carolina.
    The one prefix rule is for military mail: a complete five-digit zip in a
    military-only prefix (090-099, 340, 962-966) is AE, AA or AP.
    """
    if not zip5:
        return None
    return STATE_BY_ZIP5.get(zip5) or MILITARY_PREFIX.get(zip5[:3])


def lookup_county(zip5):
    """Look up AZ county (ACMF dropdown value) from a full 5-digit zip.

    County requires the full 5-digit zip (AZ zip prefixes span multiple
    counties), unlike state/vamc which use the 3-digit prefix. Returns None
    for non-AZ or unmapped zips (caller emits empty string).
    """
    if not zip5:
        return None
    return AZ_COUNTY_LOOKUP.get(zip5)


@app.route("/", methods=["POST"])
def zip_lookup():
    """Endpoint for TextIt webhook.

    Expects JSON body with 'zipcode' field.
    Returns JSON with 'state' and 'vamc_presumed' fields.
    """
    try:
        request_token = request.headers.get("token")
        if __API_TOKEN and (not request_token or request_token != __API_TOKEN):
            return jsonify({"status": "fail", "error": "Invalid token"}), 401

        request_json = request.get_json(silent=True) or {}

        zipcode = request_json.get("zipcode", "")
        zip5, prefix = _clean_zipcode(zipcode)

        if not prefix:
            return jsonify({
                "status": "success",
                "state": "",
                "vamc_presumed": "",
                "zip_prefix": "",
                "message": "Invalid or missing zipcode",
            }), 200

        state = lookup_state(zip5) or ""
        vamc = lookup_vamc(prefix) or ""

        return jsonify({
            "status": "success",
            "state": state,
            "vamc_presumed": vamc,
            "zip_prefix": prefix,
        }), 200

    except Exception as ex:
        logging.error(str(ex))
        return jsonify({"status": "fail", "error": str(ex)}), 500


@app.route("/county", methods=["POST"])
def county_lookup():
    """AZ ZIP -> county lookup for the ACMF Care Transition referral form.

    Expects JSON body with 'zipcode'. Returns the county as the exact string
    used in the ACMF form's county dropdown (e.g. 'Maricopa', 'Graham/Greenlee',
    'LaPaz'). Non-AZ, unmapped, or invalid zips return an empty county string
    with HTTP 200 (never an error) so the calling flow degrades gracefully.
    """
    try:
        request_token = request.headers.get("token")
        if __API_TOKEN and (not request_token or request_token != __API_TOKEN):
            return jsonify({"status": "fail", "error": "Invalid token"}), 401

        request_json = request.get_json(silent=True) or {}

        zipcode = request_json.get("zipcode", "")
        zip5, prefix = _clean_zipcode(zipcode)

        county = lookup_county(zip5) or ""

        return jsonify({
            "status": "success",
            "county": county,
            "zipcode": zip5 or "",
        }), 200

    except Exception as ex:
        logging.error(str(ex))
        return jsonify({"status": "fail", "error": str(ex)}), 500
