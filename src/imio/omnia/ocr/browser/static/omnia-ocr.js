/*
 * Start the generation of a text version from the manage panel.
 *
 * The server renders the panel (@@ocr-manage-panel).
 * A panel with a "data-ocr-process-url" attribute waits for its generation.
 * The script sends one POST request to that URL and shows the new panel.
 *
 * When the request is done, the script sends the "imio.omnia.ocr.processed"
 * event on the document. The event detail is the JSON answer of the server.
 * If the text is generated, the script reloads the page to show the text.
 * A listener can call preventDefault() on the event to stop the reload.
 *
 * The script has no dependency. Errors are silent: the panel goes back to
 * its first state.
 */
(function () {
  "use strict";

  function setBusy(panel, busy) {
    var buttons = panel.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = busy;
    }
    if (busy) {
      panel.setAttribute("aria-busy", "true");
    } else {
      panel.removeAttribute("aria-busy");
    }
  }

  function showPanel(panel, html) {
    var holder = document.createElement("div");
    holder.innerHTML = html;
    var next = holder.querySelector("[data-ocr-panel]");
    if (!next) {
      return false;
    }
    // The script does not start a second request for the new panel.
    next.setAttribute("data-ocr-started", "true");
    panel.parentNode.replaceChild(next, panel);
    return true;
  }

  function start(panel) {
    var url = panel.getAttribute("data-ocr-process-url");
    if (!url || panel.getAttribute("data-ocr-started") || !window.fetch) {
      return;
    }
    panel.setAttribute("data-ocr-started", "true");

    var label = panel.querySelector("[data-ocr-status-label]");
    var firstLabel = label ? label.textContent : "";
    var workingLabel = panel.getAttribute("data-ocr-working-label");
    if (label && workingLabel) {
      label.textContent = workingLabel;
    }
    setBusy(panel, true);

    function restore() {
      if (label) {
        label.textContent = firstLabel;
      }
      setBusy(panel, false);
    }

    var token = panel.getAttribute("data-ocr-token") || "";
    window
      .fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRF-TOKEN": token },
      })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (!data || !data.panel || !showPanel(panel, data.panel)) {
          restore();
          return;
        }
        var event = new CustomEvent("imio.omnia.ocr.processed", {
          detail: data,
          cancelable: true,
        });
        if (document.dispatchEvent(event) && data.status === "done") {
          window.location.reload();
        }
      })
      .catch(restore);
  }

  function init() {
    var panels = document.querySelectorAll("[data-ocr-panel][data-ocr-process-url]");
    for (var i = 0; i < panels.length; i++) {
      start(panels[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
