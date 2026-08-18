/* Small, dependency-free helpers. Everything here is progressive enhancement:
   the portal works with JavaScript switched off, it is just less lively. */
(function () {
  "use strict";

  // --- mobile nav ---------------------------------------------------------
  var menuBtn = document.getElementById("menuBtn");
  if (menuBtn) {
    menuBtn.addEventListener("click", function () {
      document.body.classList.toggle("nav-open");
    });
    document.addEventListener("click", function (e) {
      if (!document.body.classList.contains("nav-open")) return;
      var sidebar = document.getElementById("sidebar");
      if (sidebar && !sidebar.contains(e.target) && e.target !== menuBtn) {
        document.body.classList.remove("nav-open");
      }
    });
  }

  // --- "/" focuses search -------------------------------------------------
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) {
      var box = document.querySelector(".searchbar input");
      if (box) { e.preventDefault(); box.focus(); box.select(); }
    }
    if (e.key === "Escape") document.body.classList.remove("nav-open");
  });

  // --- tap to reveal a hidden fact ---------------------------------------
  document.querySelectorAll(".secret").forEach(function (el) {
    el.addEventListener("click", function () {
      var masked = el.querySelector(".masked");
      var real = el.querySelector(".revealed");
      if (!masked || !real) return;
      var hidden = real.style.display === "none" || !real.style.display;
      real.style.display = hidden ? "inline" : "none";
      masked.style.display = hidden ? "none" : "inline";
    });
  });

  // --- copy buttons -------------------------------------------------------
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      navigator.clipboard.writeText(text).then(function () {
        var was = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = was; }, 1200);
      });
    });
  });

  // --- confirm before destructive posts ----------------------------------
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  // --- tick ingredients off while cooking ---------------------------------
  document.querySelectorAll(".ingredients li:not(.ing-heading)").forEach(function (li) {
    li.addEventListener("click", function () { li.classList.toggle("checked"); });
  });

  // --- recipe scaler ------------------------------------------------------
  // Rewrites the quantities in place. No reload, so you can nudge the number
  // while standing at the counter and watch the list follow. The ?servings=
  // URL still works on its own for anyone without JavaScript.
  var VULGAR = [
    [1, 8, "⅛"], [1, 6, "⅙"], [1, 5, "⅕"], [1, 4, "¼"], [1, 3, "⅓"],
    [3, 8, "⅜"], [2, 5, "⅖"], [1, 2, "½"], [3, 5, "⅗"], [5, 8, "⅝"],
    [2, 3, "⅔"], [3, 4, "¾"], [4, 5, "⅘"], [5, 6, "⅚"], [7, 8, "⅞"]
  ];

  // Mirrors pretty_quantity() in portal/util.py - the two must agree, or a
  // quantity would change the moment the page reloaded.
  function prettyQuantity(value) {
    if (value === null || isNaN(value)) return "";
    if (Math.abs(value) < 1e-9) return "0";

    var best = [Math.round(value), 1], bestErr = Infinity;
    for (var d = 1; d <= 8; d++) {
      var n = Math.round(value * d);
      var err = Math.abs(value - n / d);
      if (err < bestErr - 1e-12) { bestErr = err; best = [n, d]; }
    }
    var num = best[0], den = best[1];
    // The closest eighth of a small number can be nearly double it - 0.07
    // would round to 1/8. Only use a fraction when it really is the number.
    if (Math.abs(num / den - value) > 0.02 * Math.abs(value)) {
      return String(Number(value.toFixed(2)));
    }

    var whole = Math.floor(num / den), rem = num - whole * den;
    if (rem === 0) return String(whole);

    for (var i = 0; i < VULGAR.length; i++) {
      if (VULGAR[i][0] * den === rem * VULGAR[i][1]) {
        return whole ? whole + VULGAR[i][2] : VULGAR[i][2];
      }
    }
    // toFixed rounds the same way Python's round() does on these values;
    // Math.round(v * 100) does not, and would drift by a cent on halves.
    return String(Number(value.toFixed(2)));
  }

  var scaler = document.getElementById("scaler");
  if (scaler) {
    var input = scaler.querySelector(".serving-input");
    var base = parseInt(scaler.getAttribute("data-base-servings"), 10) || 1;
    var note = document.getElementById("scaleNote");
    var factorEl = document.getElementById("scaleFactor");
    var quantities = document.querySelectorAll("#ingredientList .q");

    var apply = function (value, pushUrl) {
      var n = Math.max(1, Math.min(parseInt(value, 10) || 1, 200));
      input.value = n;

      var factor = n / base;
      quantities.forEach(function (el) {
        var q = parseFloat(el.getAttribute("data-base"));
        if (!isNaN(q)) el.textContent = prettyQuantity(q * factor);
      });

      if (note) {
        note.hidden = factor === 1;
        if (factorEl) factorEl.textContent = prettyQuantity(factor);
      }

      // Keep the address bar honest so a refresh or a shared link agrees.
      if (pushUrl !== false && window.history.replaceState) {
        var url = new URL(window.location.href);
        url.searchParams.set("servings", n);
        window.history.replaceState({}, "", url.toString());
      }
    };

    scaler.querySelectorAll("[data-servings]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        apply(btn.getAttribute("data-servings"));
      });
    });
    scaler.querySelectorAll("[data-step]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        apply(parseInt(input.value, 10) + parseInt(btn.getAttribute("data-step"), 10));
      });
    });
    if (input) {
      input.addEventListener("input", function () { apply(input.value); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); input.blur(); }
      });
    }
  }

  // --- repeating ingredient rows in the recipe editor ---------------------
  var rows = document.getElementById("ingredientRows");
  if (rows) {
    var addRow = function (heading) {
      var tpl = document.getElementById(heading ? "headingTemplate" : "rowTemplate");
      if (!tpl) return;
      rows.appendChild(tpl.content.cloneNode(true));
      var added = rows.lastElementChild;
      var focusable = added.querySelector("input[name=ing_item]");
      if (focusable) focusable.focus();
    };
    var addBtn = document.getElementById("addRow");
    var addHeadingBtn = document.getElementById("addHeading");
    if (addBtn) addBtn.addEventListener("click", function () { addRow(false); });
    if (addHeadingBtn) addHeadingBtn.addEventListener("click", function () { addRow(true); });

    rows.addEventListener("click", function (e) {
      var remove = e.target.closest("[data-remove-row]");
      if (remove) {
        e.preventDefault();
        var row = remove.closest(".row-item");
        if (row) row.remove();
      }
    });

    // Enter in the last item field adds another row instead of submitting.
    rows.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && e.target.name === "ing_item") {
        e.preventDefault();
        addRow(false);
      }
    });
  }

  // --- weather, fetched after paint --------------------------------------
  // Driven off the cards themselves rather than a wrapper, so the panels can
  // be reordered or switched off without this needing to know.
  var weatherCards = document.querySelectorAll("[data-place] .weather-body");
  if (weatherCards.length) {
    fetch("/places/api/weather", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (places) { places.forEach(renderWeather); })
      .catch(function () {
        weatherCards.forEach(function (body) {
          body.innerHTML =
            '<p class="muted tiny">Could not load weather right now.</p>';
        });
      });
  }

  function esc(value) {
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function renderWeather(place) {
    var card = document.querySelector('[data-place="' + place.id + '"]');
    if (!card) return;
    var body = card.querySelector(".weather-body");
    if (!body) return;

    var html = "";

    if (place.error && place.temp == null) {
      html += '<p class="muted tiny">' + esc(place.error) + "</p>";
      body.innerHTML = html;
      return;
    }

    html += '<div class="weather-top">';
    html += '<div class="weather-icon">' + esc(place.weather_icon) + "</div>";
    html += "<div>";
    html += '<div class="weather-temp">' +
      (place.temp == null ? "--" : esc(place.temp) + "°") + "</div>";
    html += '<div class="weather-meta">' + esc(place.text || "") + "</div>";

    var bits = [];
    if (place.humidity != null) bits.push(esc(place.humidity) + "% humidity");
    if (place.wind != null) bits.push(esc(place.wind) + " mph wind");
    if (place.heat_index != null) bits.push("feels " + esc(place.heat_index) + "°");
    if (bits.length) {
      html += '<div class="weather-meta tiny">' + bits.join(" · ") + "</div>";
    }
    html += "</div></div>";

    if (place.high_low && place.high_low.length) {
      html += '<div class="weather-strip">';
      place.high_low.forEach(function (p) {
        html +=
          '<div class="weather-day" title="' + esc(p.short || "") + '">' +
          '<div class="d-name">' + esc(p.name || "") + "</div>" +
          '<div class="d-icon">' + esc(p.icon || "") + "</div>" +
          '<div class="d-temp">' + (p.temp == null ? "--" : esc(p.temp) + "°") +
          "</div></div>";
      });
      html += "</div>";
    }

    if (place.sensors && place.sensors.length) {
      html += '<div class="sensor-row">';
      place.sensors.forEach(function (s) {
        html +=
          '<div class="sensor ' + (s.stale ? "stale" : "") + '"' +
          (s.error ? ' title="' + esc(s.error) + '"' : "") + ">" +
          "<span>" + esc(s.name) + "</span><b>" +
          (s.value == null ? "--" : esc(s.value) + esc(s.unit || "")) +
          "</b></div>";
      });
      html += "</div>";
    }

    if (place.stale) {
      html += '<p class="tiny muted mt">Last known reading — weather.gov is not answering.</p>';
    }

    body.innerHTML = html;
  }


  // --- arranging the home page -------------------------------------------
  // Drag is the enhancement; the up/down buttons and the hidden order field
  // do the same job without any of this running.
  var widgetList = document.getElementById("widgetList");
  if (widgetList) {
    var orderField = document.getElementById("orderField");

    var syncOrder = function () {
      var keys = [].slice.call(widgetList.querySelectorAll("[data-key]"))
        .map(function (row) { return row.getAttribute("data-key"); });
      orderField.value = keys.join(",");
    };

    widgetList.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-move]");
      if (!btn) return;
      var row = btn.closest(".widget-row");
      if (btn.getAttribute("data-move") === "up") {
        if (row.previousElementSibling) {
          widgetList.insertBefore(row, row.previousElementSibling);
        }
      } else if (row.nextElementSibling) {
        widgetList.insertBefore(row.nextElementSibling, row);
      }
      syncOrder();
    });

    widgetList.addEventListener("change", function (e) {
      if (e.target.type === "checkbox") {
        e.target.closest(".widget-row").classList.toggle("off", !e.target.checked);
      }
    });

    var dragged = null;
    widgetList.addEventListener("dragstart", function (e) {
      dragged = e.target.closest(".widget-row");
      if (!dragged) return;
      dragged.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      // Firefox will not start a drag without something on the transfer.
      e.dataTransfer.setData("text/plain", dragged.getAttribute("data-key"));
    });
    widgetList.addEventListener("dragend", function () {
      if (dragged) dragged.classList.remove("dragging");
      dragged = null;
      syncOrder();
    });
    widgetList.addEventListener("dragover", function (e) {
      if (!dragged) return;
      e.preventDefault();
      var over = e.target.closest(".widget-row");
      if (!over || over === dragged) return;
      var box = over.getBoundingClientRect();
      var after = (e.clientY - box.top) / box.height > 0.5;
      widgetList.insertBefore(dragged, after ? over.nextElementSibling : over);
    });
  }

  // --- weather alerts strip on the home page ------------------------------
  var alertStrip = document.getElementById("alertStrip");
  if (alertStrip) {
    fetch(alertStrip.getAttribute("data-url"), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (places) {
        var withAlerts = places.filter(function (p) { return p.alert; });
        if (!withAlerts.length) return;
        alertStrip.innerHTML = withAlerts.map(function (p) {
          var severe = p.alert.severity === "Extreme" || p.alert.severity === "Severe";
          return '<div class="alert-banner ' + (severe ? "severe" : "") + '">' +
            "<span>\u26a0\ufe0f</span><span><b>" + esc(p.alert.event) + "</b> at " +
            esc(p.name) + (p.alert.severity ? " \u00b7 " + esc(p.alert.severity) : "") +
            "</span></div>";
        }).join("");
      })
      .catch(function () { /* the weather cards already report the failure */ });
  }


  // --- inline bill edits --------------------------------------------------
  // Each cell is already a working form; this just posts it in the background
  // and repaints the row and the month totals instead of reloading.
  var billTables = document.querySelectorAll(".billtable");
  if (billTables.length) {
    document.body.classList.add("has-js");

    var postQuick = function (form, extra) {
      var data = new FormData(form);
      if (extra) Object.keys(extra).forEach(function (k) { data.set(k, extra[k]); });
      return fetch(form.action, {
        method: "POST", body: data, credentials: "same-origin",
        headers: { "X-Requested-With": "fetch" }
      }).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
    };

    var paintTotals = function (d) {
      var money = function (n) {
        return (n < 0 ? "-$" : "$") + Math.abs(Math.round(n)).toLocaleString();
      };
      var set = function (name, text) {
        var el = document.querySelector('[data-stat="' + name + '"]');
        if (el) el.textContent = text;
      };
      set("total", money(d.month_total));
      set("remaining", money(d.month_remaining));
      set("count", d.count_due);
    };

    billTables.forEach(function (table) {
      table.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-toggle]");
        if (!btn) return;
        e.preventDefault();
        var form = btn.closest("form");
        var row = btn.closest("tr");
        btn.disabled = true;
        postQuick(form).then(function (d) {
          btn.disabled = false;
          btn.textContent = d.status === "paid" ? "☑" : "☐";
          row.classList.toggle("paid", d.status === "paid");
          row.classList.toggle("overdue", d.overdue);
          var badge = row.querySelector(".pill-good, .pill-bad");
          if (badge) badge.remove();
          paintTotals(d);
        }).catch(function () { btn.disabled = false; form.submit(); });
      });

      // Amount: save when the field loses focus, or on Enter.
      table.addEventListener("focusout", function (e) {
        var input = e.target.closest("[data-amount]");
        if (!input || input.value === input.defaultValue) return;
        var form = input.closest("form");
        postQuick(form).then(function (d) {
          input.defaultValue = Number(d.amount).toFixed(2);
          input.value = input.defaultValue;
          input.classList.add("saved");
          setTimeout(function () { input.classList.remove("saved"); }, 900);
          paintTotals(d);
        }).catch(function () { form.submit(); });
      });
      table.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && e.target.closest("[data-amount]")) {
          e.preventDefault();
          e.target.blur();
        }
      });
    });
  }

  // --- radar that cannot load -------------------------------------------
  // The loop comes from weather.gov, so a server with no internet - or an
  // outage - would otherwise leave a broken-image icon sitting on the page.
  document.querySelectorAll("[data-radar]").forEach(function (img) {
    img.addEventListener("error", function () {
      var note = document.createElement("div");
      note.className = "radar-missing tiny muted";
      note.textContent = "Radar is not reachable right now. It comes straight "
        + "from weather.gov, so this needs internet access.";
      img.replaceWith(note);
    });
  });

  // --- live appearance preview -------------------------------------------
  // Applying the selection straight to :root previews the whole page, not a
  // swatch of it - which is the only honest preview, since a theme changes
  // every surface. Nothing is persisted; a reload returns to what is saved.
  (function () {
    var data = document.getElementById("lookData");
    if (!data) return;

    var look;
    try { look = JSON.parse(data.textContent); } catch (e) { return; }

    var root = document.documentElement;
    var forms = document.querySelectorAll("form#household, form#personal");
    if (!forms.length) return;

    function apply(scope) {
      var themeKey = scope.querySelector("input[name=theme]:checked");
      var fontSel = scope.querySelector("select[name=font]");
      var densitySel = scope.querySelector("select[name=density]");

      var theme = themeKey && look.themes[themeKey.value];
      if (theme) {
        Object.keys(theme.vars).forEach(function (name) {
          root.style.setProperty("--" + name, theme.vars[name]);
        });
        // data-mode drives the dark-theme card treatment, so it has to move
        // with the colours or a dark preview keeps the light card edges.
        root.setAttribute("data-mode", theme.mode);
        root.setAttribute("data-theme", themeKey.value);
      }
      if (fontSel && look.fonts[fontSel.value]) {
        root.style.setProperty("--font-body", look.fonts[fontSel.value]);
      }
      if (densitySel && look.densities[densitySel.value]) {
        root.style.setProperty("--scale", look.densities[densitySel.value]);
      }
    }

    forms.forEach(function (form) {
      form.addEventListener("change", function (e) {
        if (e.target.matches("input[name=theme], select[name=font], select[name=density]")) {
          apply(form);
        }
      });
    });
  })();

  // --- auto-submit filter selects ----------------------------------------
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });
})();
