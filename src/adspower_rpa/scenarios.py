"""Automation scenario builders for AdsPower authorization checks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .config import ServiceConfig


@dataclass(slots=True)
class AutomationStep:
    """Single step within the AdsPower automation pipeline."""

    type: str
    config: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "config": self.config}


@dataclass(slots=True)
class DiscordAuthorizationScenario:
    """Scenario definition to evaluate Discord authorization state."""

    steps: List[AutomationStep] = field(default_factory=list)

    def to_payload(self) -> List[Dict[str, Any]]:
        return [step.to_dict() for step in self.steps]


def _build_login_detection_script(service: ServiceConfig) -> str:
    """Generate a JavaScript snippet tailored to the service configuration."""

    selectors = {
        "login": service.selectors.login_indicators,
        "logout": service.selectors.logout_indicators,
        "display": service.selectors.display_name,
        "login_blocklist": service.login_path_blocklist,
    }
    serialized = json.dumps(selectors)
    target_url = json.dumps(str(service.target_url))
    template = r"""
(() => {{
  const meta = {serialized};
  const result = {{ authorized: false, displayName: '', path: location.pathname || '' }};
  try {{
    const current = String(location.href || '').trim();
    const target = {target_url};
    if (!current.startsWith(target)) {{
      result.path = new URL(current).pathname || '';
    }}
    const normalizedPath = (result.path || '').toLowerCase();
    if (Array.isArray(meta.login_blocklist)) {{
      for (const fragment of meta.login_blocklist) {{
        if (!fragment) continue;
        if (normalizedPath.includes(String(fragment).toLowerCase())) {{
          result.authorized = false;
          window.__authorization_check = result;
          return 'false';
        }}
      }}
    }}
    const hasIndicator = (selectors) => {{
      if (!Array.isArray(selectors) || !selectors.length) return false;
      return selectors.some((selector) => {{
        try {{
          return !!document.querySelector(selector);
        }} catch (error) {{
          console.debug('selector evaluation failed', selector, error);
          return false;
        }}
      }});
    }};
    result.authorized = hasIndicator(meta.login);
    if (!result.authorized && hasIndicator(meta.logout)) {{
      result.authorized = false;
    }} else if (!result.authorized) {{
      const path = normalizedPath;
      if (path && !path.includes('/login') && !path.includes('auth')) {{
        result.authorized = true;
      }}
    }}
    const collectText = (selectors) => {{
      if (!Array.isArray(selectors)) return [];
      const values = [];
      for (const selector of selectors) {{
        try {{
          const element = document.querySelector(selector);
          if (!element) continue;
          const text = (element.getAttribute('aria-label') || element.textContent || '').trim();
          if (text) values.push(text);
        }} catch (_) {{}}
      }}
      return values;
    }};
    const names = collectText(meta.display)
      .map((text) => text.replace(/[\u200d\u200c\u200b\u200e\u200f\uFE0F]/g, '').replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    if (names.length) {{
      result.displayName = names[0];
    }}
  }} catch (error) {{
    console.error('authorization detection failed', error);
  }}
  window.__authorization_check = result;
  return result.authorized ? 'true' : 'false';
}})();
"""
    return template.format(serialized=serialized, target_url=target_url).strip()


def _profile_serial_script() -> str:
    script = r"""
(() => {
  const bucket = new Set();
  const push = (value) => {
    if (value === undefined || value === null) return;
    const text = String(value).trim();
    if (!text) return;
    bucket.add(text);
  };
  const inspectObject = (obj) => {
    if (!obj || typeof obj !== 'object') return;
    for (const key of ['serialNumber', 'serial_number', 'profileSerial', 'id', 'serial']) {
      if (key in obj) push(obj[key]);
    }
  };
  try {
    const globals = ['profileInfo', 'profile_info', 'AdsPowerProfile', 'AdsPower', 'adsPower', 'apx'];
    for (const key of globals) {
      try {
        const candidate = window[key];
        inspectObject(candidate);
        if (candidate && typeof candidate === 'object') {
          inspectObject(candidate.profileInfo);
          inspectObject(candidate.profile_info);
        }
      } catch (_) {}
    }
    const storageScan = (storage) => {
      if (!storage || typeof storage.length !== 'number') return;
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        if (!key || !/serial|profile|ads/i.test(key)) continue;
        let value = null;
        try {
          value = storage.getItem(key);
        } catch (_) {
          continue;
        }
        if (!value) continue;
        try {
          const parsed = JSON.parse(value);
          inspectObject(parsed);
        } catch (_) {
          const match = String(value).match(/serial(?:Number|_number)?['"=:\\s]*([A-Za-z0-9._-]+)/i);
          if (match && match[1]) push(match[1]);
        }
      }
    };
    storageScan(window.localStorage);
    storageScan(window.sessionStorage);
    if (typeof window.name === 'string') {
      const match = window.name.match(/serial(?:Number|_number)?[:=]?([A-Za-z0-9._-]+)/i);
      if (match && match[1]) push(match[1]);
    }
  } catch (error) {
    console.warn('profile serial detection failed', error);
  }
  const ordered = Array.from(bucket).sort((a, b) => b.length - a.length || a.localeCompare(b));
  const serial = ordered[0] || '';
  window.__authorization_profile_serial = serial;
  return serial;
})();
"""
    return script.strip()


def _nickname_script() -> str:
    script = r"""
(() => {
  const info = window.__authorization_check;
  if (info && typeof info.displayName === 'string') {
    return info.displayName;
  }
  return '';
})();
"""
    return script.strip()


def build_discord_authorization_scenario(service: ServiceConfig) -> DiscordAuthorizationScenario:
    """Create an automation scenario capable of validating Discord authorization."""

    scenario = DiscordAuthorizationScenario()
    scenario.steps.extend(
        [
            AutomationStep(
                type="waitTime",
                config={
                    "timeoutType": "fixedValue",
                    "timeout": 2000,
                    "remark": "stabilize environment",
                },
            ),
            AutomationStep(type="newPage", config={}),
            AutomationStep(
                type="closeOtherPage",
                config={"keepCurrent": True, "remark": "ensure single active tab"},
            ),
            AutomationStep(
                type="gotoUrl",
                config={
                    "url": str(service.target_url),
                    "timeout": 45000,
                    "waitUntil": "load",
                    "remark": f"open {service.name} target page",
                },
            ),
            AutomationStep(
                type="waitTime",
                config={
                    "timeoutType": "randomInterval",
                    "timeoutMin": 3000,
                    "timeoutMax": 6000,
                    "remark": "allow interface to settle",
                },
            ),
            AutomationStep(
                type="javaScript",
                config={
                    "params": [],
                    "content": _build_login_detection_script(service),
                    "variable": "service_authorized",
                    "remark": "detect authorization state",
                },
            ),
            AutomationStep(
                type="javaScript",
                config={
                    "params": [],
                    "content": _nickname_script(),
                    "variable": "service_display_name",
                    "remark": "capture display name",
                },
            ),
            AutomationStep(
                type="javaScript",
                config={
                    "params": [],
                    "content": _profile_serial_script(),
                    "variable": "profile_serial",
                    "remark": "detect profile serial",
                },
            ),
            AutomationStep(type="closeBrowser", config={}),
        ]
    )
    return scenario


__all__ = [
    "AutomationStep",
    "DiscordAuthorizationScenario",
    "build_discord_authorization_scenario",
]
