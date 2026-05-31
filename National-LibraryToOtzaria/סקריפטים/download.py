"""SSO login flow for fjms.genizah.org / rambam.genizah.org.

Replicates the JSONP-based login sequence used by the site:
  1. GetLoginUIT  -> exchange username/password for UIT token
  2. GetUserPermission -> fetch permission flags
  3. GetUserInfo  -> fetch profile info
  4. Use UIT as querystring param when hitting protected endpoints.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

SSO_BASE = "https://sso.genizah.org"
FJMS_BASE = "https://fjms.genizah.org"
RAMBAM_BASE = "https://rambam.genizah.org"

LOGIN_STATUS = {
    0: "canLogin",
    1: "userNotFound",
    2: "pwdIncorrect",
    3: "userUnapproved",
    4: "userLockedOut",
    5: "refusedEmail",
    6: "instNoIps",
    7: "instIpNotAllowed",
    8: "instTooManyEntries",
    9: "userNoFullConditions",
    10: "userNoFullProfile",
    11: "canLoginAsGuest",
}

_JSONP_RE = re.compile(r"^[^(]*\((.*)\)\s*;?\s*$", re.DOTALL)


def _parse_jsonp(text: str) -> Any:
    m = _JSONP_RE.match(text.strip())
    if not m:
        raise ValueError(f"Not a JSONP response: {text[:120]!r}")
    return json.loads(m.group(1))


@dataclass
class Session:
    username: str
    password: str
    lang: str = "heb"
    screen_width: int = 1600
    http: requests.Session = field(default_factory=requests.Session)
    uit: str | None = None
    permissions: dict | None = None
    user_info: dict | None = None

    def __post_init__(self) -> None:
        self.http.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Referer": f"{FJMS_BASE}/",
            "Accept": "*/*",
        })

    def _jsonp_get(self, path: str, params: dict | None = None) -> Any:
        params = dict(params or {})
        params.setdefault("callback", "cb")
        r = self.http.get(f"{SSO_BASE}/{path.lstrip('/')}", params=params, timeout=15)
        r.raise_for_status()
        return _parse_jsonp(r.text)

    def get_login_uit(self) -> dict:
        res = self._jsonp_get("login/GetLoginUIT", {
            "screenWidth": self.screen_width,
            "username": self.username,
            "password": self.password,
        })
        status = res.get("Status")
        if status != 0:
            raise RuntimeError(f"Login failed: status={status} ({LOGIN_STATUS.get(status, 'unknown')})")
        self.uit = res["UIT"]
        return res

    def get_permission(self) -> dict:
        res = self._jsonp_get("User/GetUserPermission", {"UIT": self.uit})
        self.permissions = res
        return res

    def get_user_info(self) -> dict:
        res = self._jsonp_get("user/GetUserInfo", {"UIT": self.uit, "lang": self.lang})
        self.user_info = res
        return res

    def login(self) -> dict:
        self.get_login_uit()
        self.get_permission()
        self.get_user_info()
        return {"UIT": self.uit, "permissions": self.permissions, "user": self.user_info}

    def site_url(self, base: str) -> str:
        if not self.uit:
            raise RuntimeError("login() first")
        return f"{base}/Account/SSOSignIn?lang={self.lang}&UIT={self.uit}"

    def signin_to(self, base: str) -> requests.Response:
        """Exchange UIT for a target-site session cookie.

        Hits /Account/SSOSignIn?UIT=... so the target site mints its own
        ASP.NET session cookie bound to this user. Without this step the
        target APIs return 403 even with a valid UIT.
        """
        if not self.uit:
            raise RuntimeError("login() first")
        assert self.http is not None
        r = self.http.get(
            f"{base}/Account/SSOSignIn",
            params={"lang": self.lang, "UIT": self.uit},
            headers={"Referer": f"{FJMS_BASE}/"},
            allow_redirects=True,
            timeout=15,
        )
        r.raise_for_status()
        return r

    def get_divisions(self, level: int = 1, parent_id: int | None = None) -> list:
        url = f"https://rambam.genizah.org/api/SelectionControlAPI/GetDivisions?levelId={level}&parentIds%5B0%5D={parent_id or ''}&inProjectId=&useFtsSession=false"
        headers = {
            "User-Agent": "Mozilla/5.0",
        }
        res = self.http.get(url, headers=headers, timeout=15, params=None)
        return res.json()

    def get_mefarshim_by_division_detail_id(self, division_detail_id: int) -> dict:
        url = f"https://rambam.genizah.org/api/DiffAPI/GetMefarshimByDivisionDetailId?DivisionDetailId={division_detail_id}"
        headers = {
            "User-Agent": "Mozilla/5.0",
        }
        res = self.http.get(url, headers=headers, timeout=15, params=None)
        return res.json()


if __name__ == "__main__":
    user_name = os.environ.get("GENIZAH_USERNAME", "")
    password = os.environ.get("GENIZAH_PASSWORD", "")
    if not user_name or not password:
        raise SystemExit("Set GENIZAH_USERNAME and GENIZAH_PASSWORD in .env or environment")
    sess = Session(
        username=user_name,
        password=password,
    )
    sess.login()
    sess.signin_to(RAMBAM_BASE)  # mints rambam ASP.NET session
    sess.site_url(RAMBAM_BASE)
    level_1 = sess.get_divisions(level=1)

    with open("output_2.json", "w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        bar_l1 = tqdm(level_1, unit="item")
        for sub_level in bar_l1:
            bar_l1.set_description(f"ספר [{sub_level['Desc']}]")
            level_id = sub_level["Id"]
            if level_id < 1:
                continue
            level_1_data = sub_level
            level_1_data["sub_levels"] = []
            level_2 = sess.get_divisions(level=2, parent_id=level_id)
            bar_l2 = tqdm(level_2, unit="item", leave=False)
            for sub_level_2 in bar_l2:
                bar_l2.set_description(f"הלכות [{sub_level_2['Desc']}]")
                sub_id = sub_level_2["Id"]
                if sub_id < 1:
                    continue
                level_2_data = sub_level_2
                level_2_data["sub_levels"] = []
                level_3 = sess.get_divisions(level=3, parent_id=sub_id)
                bar_l3 = tqdm(level_3, unit="item", leave=False)
                for sub_level_3 in bar_l3:
                    bar_l3.set_description(f"פרק [{sub_level_3['Desc']}]")
                    sub_id_3 = sub_level_3["Id"]
                    if sub_id_3 < 1:
                        continue
                    level_3_data = sub_level_3
                    level_3_data["sub_levels"] = []
                    level_4 = sess.get_divisions(level=4, parent_id=sub_id_3)
                    bar_l4 = tqdm(level_4, unit="item", leave=False)
                    for sub_level_4 in bar_l4:
                        bar_l4.set_description(f"הלכה [{sub_level_4['Desc']}]")
                        division_detail_id = sub_level_4["Id"]
                        if division_detail_id < 1:
                            continue
                        level_4_data = sub_level_4
                        res = sess.get_mefarshim_by_division_detail_id(division_detail_id).get("arrDivisionAllMefarshim")
                        level_4_data["mefarshim"] = res
                        level_3_data["sub_levels"].append(level_4_data)
                    level_2_data["sub_levels"].append(level_3_data)
                level_1_data["sub_levels"].append(level_2_data)
            if not first:
                f.write(",\n")
            json.dump(level_1_data, f, ensure_ascii=False, indent=2)
            f.flush()
            first = False
            level_1_data.clear()
        f.write("\n]\n")
