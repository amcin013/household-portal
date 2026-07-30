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

  // --- dashboard weather, fetched after paint ----------------------------
  var weatherHost = document.getElementById("weatherCards");
  if (weatherHost) {
    fetch(weatherHost.getAttribute("data-url"), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (places) { places.forEach(renderWeather); })
      .catch(function () {
        weatherHost.querySelectorAll("[data-place]").forEach(function (card) {
          var body = card.querySelector(".weather-body");
          if (body) {
            body.innerHTML =
              '<p class="muted tiny">Could not load weather right now.</p>';
          }
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

    if (place.alert) {
      html +=
        '<div class="alert-banner ' +
        (place.alert.severity === "Extreme" || place.alert.severity === "Severe"
          ? "severe" : "") +
        '"><span>⚠️</span><span><b>' + esc(place.alert.event) + "</b>" +
        (place.alert.severity ? " · " + esc(place.alert.severity) : "") +
        "</span></div>";
    }

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

  // --- auto-submit filter selects ----------------------------------------
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });
})();
