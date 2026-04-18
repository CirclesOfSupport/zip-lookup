from flask import Flask, request, jsonify
import logging
import os
from urllib.parse import unquote

from state_lookup import STATE_LOOKUP, STATE_LOOKUP_5DIGIT
from vamc_lookup import VAMC_LOOKUP

__API_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")

logging.basicConfig(level="DEBUG")

app = Flask(__name__)

logging.info(f"State lookup ready: {len(STATE_LOOKUP)} prefix entries, {len(STATE_LOOKUP_5DIGIT)} 5-digit overrides")
logging.info(f"VAMC lookup ready: {len(VAMC_LOOKUP)} entries")


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


def lookup_state(zip5, prefix):
    """Look up state from a zipcode.

    Tries 5-digit override first (for territories sharing a prefix),
    then 3-digit exact match, then nearest prefix fallback.
    """
    if zip5 and zip5 in STATE_LOOKUP_5DIGIT:
        return STATE_LOOKUP_5DIGIT[zip5]
    result = STATE_LOOKUP.get(prefix)
    if result:
        return result
    return _nearest_match(prefix, STATE_LOOKUP)


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

        state = lookup_state(zip5, prefix) or ""
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
