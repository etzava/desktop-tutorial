"""
Client για SoftOne Web Services (Soft1 Series 5 / Cloud).

Ροή:  login -> authenticate -> SqlData / getBrowserInfo+getBrowserData / getTable
Endpoint: https://<serial>.oncloud.gr/s1services   (ή το δικό σας on-prem URL)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger(__name__)


class SoftOneError(RuntimeError):
    pass


@dataclass
class SoftOneConfig:
    url: str                      # π.χ. https://12345678.oncloud.gr/s1services
    username: str
    password: str
    app_id: str                   # appId από τη ρύθμιση Web Services του SoftOne
    company: str | None = None    # αν None -> παίρνει την 1η εταιρεία του login
    branch: str | None = None
    module: str | None = None
    refid: str | None = None
    timeout: int = 60
    verify_ssl: bool = True


@dataclass
class SoftOneClient:
    cfg: SoftOneConfig
    client_id: str | None = None
    session: requests.Session = field(default_factory=requests.Session)

    # ---------------------------------------------------------------- low level
    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.session.post(
            self.cfg.url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=self.cfg.timeout,
            verify=self.cfg.verify_ssl,
        )
        resp.raise_for_status()
        raw = resp.content
        # Το SoftOne επιστρέφει συχνά windows-1253 αντί για UTF-8
        for enc in ("utf-8", "cp1253"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")
        data = json.loads(text)
        if not data.get("success", False):
            raise SoftOneError(f"{payload.get('service')}: {data.get('error') or data}")
        return data

    def _call(self, payload: dict[str, Any], _retry: bool = True) -> dict[str, Any]:
        """Κλήση με αυτόματο re-login αν έληξε το session."""
        if not self.client_id:
            self.connect()
        payload = {**payload, "clientID": self.client_id, "appId": self.cfg.app_id}
        try:
            return self._post(payload)
        except SoftOneError as e:
            msg = str(e).lower()
            if _retry and any(k in msg for k in ("session", "clientid", "expired", "-101", "authenticate")):
                log.info("Session expired – re-login")
                self.client_id = None
                return self._call(payload, _retry=False)
            raise

    # ------------------------------------------------------------------- auth
    def connect(self) -> str:
        login = self._post({
            "service": "login",
            "username": self.cfg.username,
            "password": self.cfg.password,
            "appId": self.cfg.app_id,
        })
        objs = login.get("objs") or []
        if not objs:
            raise SoftOneError("Το login δεν επέστρεψε εταιρείες (objs).")
        pick = next(
            (o for o in objs if self.cfg.company is None or str(o.get("COMPANY")) == str(self.cfg.company)),
            objs[0],
        )
        auth = self._post({
            "service": "authenticate",
            "clientID": login["clientID"],
            "COMPANY": self.cfg.company or pick.get("COMPANY"),
            "BRANCH": self.cfg.branch or pick.get("BRANCH"),
            "MODULE": self.cfg.module or pick.get("MODULE", "0"),
            "REFID": self.cfg.refid or pick.get("REFID"),
        })
        self.client_id = auth["clientID"]
        return self.client_id

    # --------------------------------------------------------------- services
    def sql_data(self, sql_name: str, **params: Any) -> list[dict[str, Any]]:
        """Εκτελεί αποθηκευμένο SQL script του SoftOne (service SqlData).
        Οι παράμετροι περνάνε ως param1, param2, ... (όπως ορίζονται στο script)."""
        data = self._call({"service": "SqlData", "SqlName": sql_name, **params})
        return data.get("rows") or []

    def get_table(self, table: str, fields: str, filter_: str = "") -> list[dict[str, Any]]:
        """Απλό ανάγνωσμα πίνακα (service getTable)."""
        data = self._call({"service": "getTable", "TABLE": table, "FIELDS": fields, "FILTER": filter_})
        cols = [c.get("name") or c.get("NAME") for c in data.get("model", [[]])[0]] if data.get("model") else None
        rows = data.get("data") or []
        if cols and rows and isinstance(rows[0], list):
            return [dict(zip(cols, r)) for r in rows]
        return rows

    def browser(self, obj: str, list_name: str = "", filters: str = "", limit: int = 100000) -> list[dict[str, Any]]:
        """Διαβάζει ένα browser/λίστα (π.χ. SALDOC) – getBrowserInfo + getBrowserData."""
        info = self._call({"service": "getBrowserInfo", "OBJECT": obj, "LIST": list_name, "FILTERS": filters})
        cols = [f.get("name") for f in info.get("fields", [])]
        out: list[dict[str, Any]] = []
        start, page = 0, 5000
        while start < min(info.get("totalcount", 0), limit):
            d = self._call({"service": "getBrowserData", "reqID": info["reqID"], "START": start, "LIMIT": page})
            for r in d.get("rows", []):
                out.append(dict(zip(cols, r)))
            start += page
        return out
