// Python renders the pages and applies all access and employee-management rules.
const $ = (id) => document.getElementById(id);
let token = null,
  user = null,
  view = "workspace",
  offset = 0,
  busy = false,
  expiryTimer;
const roles = {
  admin: "Administrator",
  employee: "Employee",
  data_analyst: "Data analyst",
  security_engineer: "Security engineer",
};
const icons = () => window.lucide && lucide.createIcons();
function message(result) {
  if (result.status === 429)
    return (
      "Too many attempts. Try again in " + (result.retry || 60) + " seconds."
    );
  const detail = result.data?.detail;
  return typeof detail === "string"
    ? detail
    : Array.isArray(detail)
      ? detail.map((e) => e.msg).join("; ")
      : "Request failed. Please try again.";
}
function identity() {
  $("account-heading").textContent = user ? "Your employee profile" : "Employee sign in";
  document.body.classList.toggle("authenticated", !!user);
  $("signed-in").hidden = !user;
  $("signed-out").hidden = !!user;
  $("header-name").textContent = user?.name.split(" ")[0] || "Guest";
  $("header-avatar").textContent = user?.name[0] || "S";
  $("session-metric").textContent = user ? "Active" : "Signed out";
  $("role-metric").textContent = user ? roles[user.role] : "Guest";
  $("user-name").textContent = user?.name || "";
  $("user-email").textContent = user?.email || "";
  $("avatar").textContent = user?.name[0] || "";
  $("user-role").textContent = user ? roles[user.role] : "";
  $("employee-id").textContent = user
    ? "SK-" + String(user.id).padStart(3, "0")
    : "";
  const headings = {
    workspace: [
      "Overview",
      user
        ? "Welcome back, " + user.name.split(" ")[0] + "."
        : "Welcome to Sankalpa.AI.",
    ],
    people: ["People", "Our people"],
    activity: ["Activity log", "Workspace activity"],
    account: ["My account", "My account"],
  };
  $("breadcrumb").textContent = headings[view][0];
  $("page-title").textContent = headings[view][1];
}
function signOut(note = "") {
  token = user = null;
  clearTimeout(expiryTimer);
  $("records-fragment").replaceChildren();
  $("account-fragment").replaceChildren();
  $("record-message").textContent = "Sign in to continue.";
  $("response-body").textContent = "No response yet.";
  $("request-path").textContent = "No request";
  $("request-time").textContent = "";
  $("trace-identity").textContent = "Not signed in";
  $("trace-token").textContent = "No token";
  $("trace-decision").textContent = "Awaiting request";
  $("decision-summary").textContent =
    "No application requests in this session.";
  $("response-status").textContent = "Waiting";
  $("response-status").className = "badge neutral";
  document.querySelectorAll(".app-result").forEach((el) => {
    el.textContent = "Prototype";
    el.className = "badge neutral app-result";
  });
  $("account-message").textContent = note;
  $("expires").textContent = "";
  identity();
}
async function api(method, path, body, html = false) {
  try {
    const headers = token ? { Authorization: "Bearer " + token } : {};
    if (body) headers["Content-Type"] = "application/json";
    const response = await fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data =
      html && response.ok ? await response.text() : await response.json();
    if (response.status === 401 && token)
      signOut("Session expired or account inactive. Please sign in.");
    return {
      ok: response.ok,
      status: response.status,
      data,
      retry: response.headers.get("Retry-After"),
    };
  } catch {
    return {
      ok: false,
      status: 0,
      data: { detail: "Sudarshan is unavailable. Please try again." },
    };
  }
}
async function run(task) {
  if (busy) return;
  busy = true;
  const buttons = [...document.querySelectorAll("button")].map((button) => [
    button,
    button.disabled,
  ]);
  buttons.forEach(([button]) => {
    button.disabled = true;
  });
  try {
    await task();
  } finally {
    buttons.forEach(([button, disabled]) => {
      button.disabled = disabled;
    });
    busy = false;
    icons();
  }
}
async function loadView() {
  if (view === "workspace") return;
  const isAccount = view === "account";
  const target = isAccount ? $("account-fragment") : $("records-fragment");
  target.replaceChildren();
  const params = new URLSearchParams();
  if (!isAccount) {
    for (const [key, value] of new FormData($("record-filters"))) {
      if (
        value &&
        (view === "people" ? ["search", "role"].includes(key) : key !== "role")
      )
        params.set(key, value);
    }
    params.set("offset", offset);
    $("record-message").textContent = "Loading...";
  }
  const result = await api(
    "GET",
    "/workspace/" + view + (params.size ? "?" + params : ""),
    null,
    true,
  );
  if (result.ok) {
    target.innerHTML = result.data; // Trusted, autoescaped Jinja output from our server.
    $("record-message").textContent = "";
  } else {
    const p = document.createElement("p");
    p.className = "empty-state";
    p.textContent = message(result);
    target.append(p);
    $("record-message").textContent = result.status
      ? "HTTP " + result.status
      : "Offline";
  }
}
async function navigate(next) {
  await run(async () => {
    view = next;
    offset = 0;
    identity();
    document.querySelectorAll("[data-view]").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === view);
      button.setAttribute(
        "aria-current",
        button.dataset.view === view ? "page" : "false",
      );
    });
    $("workspace-view").hidden = view !== "workspace";
    $("records-view").hidden = !["people", "activity"].includes(view);
    $("account-view").hidden = view !== "account";
    $("role-filter").hidden = view !== "people";
    $("audit-filters").hidden = view !== "activity";
    $("record-filters").reset();
    $("records-title").textContent =
      view === "people" ? "Employee directory" : "Security events";
    await loadView();
  });
}
$("account-form").onsubmit = (event) => {
  event.preventDefault();
  run(async () => {
    $("account-message").textContent = "Signing in...";
    const result = await api("POST", "/auth/login", {
      email: $("email").value,
      password: $("password").value,
    });
    if (!result.ok) {
      $("account-message").textContent = message(result);
      return;
    }
    token = result.data.access_token;
    const profile = await api("GET", "/users/me");
    if (!profile.ok) {
      signOut(message(profile));
      return;
    }
    user = profile.data;
    identity();
    $("password").value = "";
    $("account-message").textContent = "";
    const payload = JSON.parse(
      atob(token.split(".")[1].replaceAll("-", "+").replaceAll("_", "/")),
    );
    $("expires").textContent = new Date(
      payload.exp * 1000,
    ).toLocaleTimeString();
    clearTimeout(expiryTimer);
    expiryTimer = setTimeout(
      () => signOut("Session expired."),
      Math.max(0, payload.exp * 1000 - Date.now()),
    );
    await loadView();
  });
};
$("demo").onchange = () => {
  $("email").value = $("demo").value;
  $("password").value = "DemoPass123!";
};
$("toggle-password").onclick = () => {
  const show = $("password").type === "password";
  $("password").type = show ? "text" : "password";
  $("toggle-password").title = show ? "Hide password" : "Show password";
  $("toggle-password").setAttribute("aria-label", $("toggle-password").title);
};
$("logout").onclick = () => signOut("Signed out of Sankalpa.AI.");
document.querySelectorAll("[data-view]").forEach((button) => {
  button.onclick = () => navigate(button.dataset.view);
  button.title = button.textContent.trim();
});
$("refresh-records").onclick = () => run(loadView);
$("profile").onclick = () => run(loadView);
$("record-filters").onsubmit = (event) => {
  event.preventDefault();
  offset = 0;
  run(loadView);
};
document.addEventListener("click", (event) => {
  const pager = event.target.closest("[data-offset]");
  if (pager)
    run(async () => {
      offset = Number(pager.dataset.offset);
      await loadView();
    });
  const app = event.target.closest("[data-app]");
  if (app)
    run(async () => {
      const start = performance.now(),
        result = await api("POST", app.dataset.app),
        badge = app.closest("article").querySelector(".app-result");
      badge.textContent = result.ok
        ? "Access granted"
        : result.status === 403
          ? "Access denied"
          : result.status === 401
            ? "Sign in required"
            : "Unavailable";
      badge.className =
        "badge app-result " + (result.ok ? "success" : "danger");
      $("response-status").textContent = "HTTP " + result.status;
      $("response-status").className =
        "badge " + (result.ok ? "success" : "danger");
      $("trace-identity").textContent = user?.name || "Not signed in";
      $("trace-token").textContent = token ? "JWT sent" : "No token";
      $("trace-decision").textContent = result.ok ? "Granted" : "Denied";
      $("decision-summary").textContent = result.ok
        ? "Access granted. This agent is a prototype."
        : message(result);
      $("request-path").textContent = "POST " + app.dataset.app;
      $("request-time").textContent =
        Math.round(performance.now() - start) + " ms";
      $("response-body").textContent = JSON.stringify(result.data, null, 2);
    });
});
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-api]");
  if (!form) return;
  event.preventDefault();
  run(async () => {
    const data = Object.fromEntries(new FormData(form));
    if (form.querySelector("[name=is_active]"))
      data.is_active = form.elements.is_active.checked;
    const result = await api(form.dataset.method, form.dataset.api, data),
      status = form.querySelector(".form-message");
    status.textContent = result.ok
      ? result.data.message || "Saved successfully."
      : message(result);
    if (result.ok) {
      form.querySelectorAll("input[type=password]").forEach((input) => {
        input.value = "";
      });
      if (form.dataset.method === "PATCH") {
        form.closest("tr").classList.add("saved");
      }
      if (form.dataset.api === "/admin/users") {
        form.reset();
        await loadView();
        $("record-message").textContent = "Employee created successfully.";
      }
    }
  });
});
async function health() {
  let ok = false;
  try {
    ok = (await fetch("/health")).ok;
  } catch {}
  $("health").textContent = ok
    ? "All systems operational"
    : "Service unavailable";
}
$("today").textContent = new Date().toLocaleDateString(undefined, {
  weekday: "short",
  month: "short",
  day: "numeric",
  year: "numeric",
});
identity();
icons();
health();
setInterval(health, 30000);
