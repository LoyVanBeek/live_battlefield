/* Shared Leaflet location editor.
 *
 * Owns the map + numbered pins, the locations table (inline editing of code /
 * coordinates / bombs), the per-location quiz modal and toasts. Persistence is
 * host-supplied through an adapter, so the GM locations page (server-backed,
 * one request per action) and the admin location-set editor (a client-side
 * draft saved as a whole) reuse one editor.
 *
 * Requires leaflet.js, location-pin.js and quiz_editor.js to be loaded first.
 *
 * Usage:
 *   const editor = createLocationEditor({
 *     els: {
 *       map: 'map', tbody: 'locations-body', mapHint: 'map-hint', toast: 'toast',
 *       quizModal: 'lq-modal', quizTitle: 'lq-modal-title', quizMode: 'lq-mode',
 *       quizQuestionsList: 'lq-questions-list', quizWarningBanner: 'lq-warning-banner',
 *     },
 *     showVisitedBy: true,                 // render the "Visited By" column
 *     renderVisited: loc => '…',           // required when showVisitedBy
 *     codeRequired: true,                  // false lets codes stay blank (generated on save)
 *     onLoaded: (locations, data) => {},   // after every load()
 *     onQuizOpen: number => {},            // whenever the quiz modal opens
 *     adapter: {
 *       load:      async () => ({ locations: [...], …extra }),
 *       add:       async ({ latitude, longitude, count, radiusKm }) => ({ success, message }),
 *       remove:    async number => ({ success, message }),
 *       clearAll:  async () => ({ success, message }),
 *       saveField: async (number, field, value) => ({ success, message }),
 *       loadQuiz:  async number => ({ success, mode, questions, message }),
 *       saveQuiz:  async (number, mode, questions) => ({ success, message }),
 *     },
 *   });
 *   editor.load();
 */
(function () {
    "use strict";

    const BOXTEL_CENTER = [51.59, 5.33];

    function createLocationEditor(config) {
        config = config || {};
        const els = config.els || {};
        const adapter = config.adapter || {};
        const showVisitedBy = !!config.showVisitedBy;
        const codeRequired = config.codeRequired !== false;
        const renderVisited = config.renderVisited || (() => "");
        const onLoaded = config.onLoaded || (() => {});
        const onQuizOpen = config.onQuizOpen || (() => {});

        // #, code, coords, bombs [, visited], quiz, map, action
        const columns = 4 + (showVisitedBy ? 1 : 0) + 3;

        let map = null;
        let markers = [];
        let editing = null;
        let quizNumber = null;

        const byId = (id) => (id ? document.getElementById(id) : null);

        function escapeHtml(s) {
            return String(s).replace(/[&<>"']/g, (c) =>
                ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
            );
        }

        function showToast(msg, type = "success") {
            const toast = byId(els.toast);
            if (!toast) return;
            toast.textContent = msg;
            toast.className = "";
            void toast.offsetWidth; // restart animation
            toast.className = (type === "success" ? "success" : "error") + " show";
            clearTimeout(showToast._t);
            showToast._t = setTimeout(() => { toast.className = ""; }, 3000);
        }

        function updateMapHint() {
            const hint = byId(els.mapHint);
            if (!hint) return;
            hint.textContent = (editing && editing.field === "coords")
                ? "🖱️ Click map or drag marker to set position"
                : "🖱️ Click map to add location";
        }

        function quizModeLabel(mode) {
            if (mode === "quiz") return "📝 Quiz";
            if (mode === "both") return "📝+🔑 Both";
            return "🔑 Code";
        }

        // A location in "quiz" mode has no printed code, so its code and
        // code-mode bomb reward are hidden. "code" and "both" still show them.
        function hasCodeMode(loc) {
            return (loc.quiz_mode || "code") !== "quiz";
        }

        function locationPopup(loc) {
            const head = `<b>Location ${loc.number}</b>`;
            if (!hasCodeMode(loc)) return head + "<br>Quiz only";
            return head + `<br>Code: ${loc.code}<br>Bombs: ${loc.bomb_value || 1}`;
        }

        const quizEditor = createQuizEditor({
            listId: els.quizQuestionsList,
            warningId: els.quizWarningBanner,
            addAnswerLabel: "Add Answer",
            toast: showToast,
        });

        function initMap() {
            map = L.map(els.map).setView(BOXTEL_CENTER, 13);

            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution: "&copy; OpenStreetMap contributors",
            }).addTo(map);

            map.on("click", (e) => {
                // While the coords editor is open, a map click picks the new
                // position instead of creating a location.
                if (editing && editing.field === "coords") {
                    const input = byId("cell-edit-input");
                    if (input) {
                        input.value = `${e.latlng.lat}, ${e.latlng.lng}`;
                        input.focus();
                    }
                    return;
                }
                addLocations({ latitude: e.latlng.lat, longitude: e.latlng.lng, count: 1, radiusKm: 0 })
                    .then((data) => {
                        if (!data.success) alert(data.message || "Error adding location");
                    });
            });
        }

        function updateMarkers(locations) {
            markers.forEach((m) => map.removeLayer(m));
            markers = [];

            locations.forEach((loc) => {
                const marker = L.marker([loc.latitude, loc.longitude], {
                    icon: locationPinIcon(loc.number),
                })
                    .addTo(map)
                    .bindPopup(locationPopup(loc));
                marker.locationNumber = loc.number;
                markers.push(marker);
            });
        }

        function renderRow(loc) {
            const lat = loc.latitude.toFixed(4);
            const lon = loc.longitude.toFixed(4);
            const mapUrl = `https://maps.google.com/?q=${loc.latitude},${loc.longitude}`;

            const quizCount = loc.question_count != null
                ? loc.question_count
                : (loc.questions || []).length;
            const quizLabel = quizModeLabel(loc.quiz_mode) + (quizCount ? ` (${quizCount})` : "");

            // Quiz-only locations have no code and no code-mode bomb reward,
            // so those cells show a muted placeholder instead.
            const codeMode = hasCodeMode(loc);
            const codeCell = codeMode
                ? `<span class="editable-cell" id="cell-code-${loc.number}" data-edit="code" data-number="${loc.number}">${loc.code || ""}</span>`
                : `<span class="not-visited" title="Set this location to Code or Both to see its code">—</span>`;
            const bombsCell = codeMode
                ? `<span class="editable-cell" id="cell-bombs-${loc.number}" data-edit="bombs" data-number="${loc.number}">💣 ${loc.bomb_value || 1}</span>`
                : `<span class="not-visited" title="Set this location to Code or Both to see its bombs">—</span>`;

            const visitedCell = showVisitedBy ? `<td class="visited">${renderVisited(loc)}</td>` : "";

            return `
                <tr>
                    <td>${loc.number}</td>
                    <td class="code">${codeCell}</td>
                    <td class="coords"><span class="editable-cell" id="cell-coords-${loc.number}" data-lat="${loc.latitude}" data-lon="${loc.longitude}" data-edit="coords" data-number="${loc.number}">${lat}, ${lon}</span></td>
                    <td>${bombsCell}</td>
                    ${visitedCell}
                    <td><span class="editable-cell" id="cell-quiz-${loc.number}" data-quiz="${loc.number}" title="Edit this location's check-in quiz">${quizLabel}</span></td>
                    <td><a class="map-link" href="${mapUrl}" target="_blank">Map</a></td>
                    <td><button class="btn-remove" data-remove="${loc.number}" data-code="${escapeHtml(loc.code || "")}">Remove</button></td>
                </tr>`;
        }

        async function load() {
            if (!map) initMap();

            try {
                const data = await adapter.load();
                const locations = (data && data.locations) || [];
                onLoaded(locations, data);

                const tbody = byId(els.tbody);
                updateMarkers(locations);

                if (locations.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="${columns}" style="text-align: center;">No locations found</td></tr>`;
                    return;
                }
                tbody.innerHTML = locations.map(renderRow).join("");
            } catch (e) {
                console.error("Error loading locations:", e);
                const tbody = byId(els.tbody);
                if (tbody) {
                    tbody.innerHTML = `<tr><td colspan="${columns}" style="text-align: center;">Error loading locations</td></tr>`;
                }
            }
        }

        // While the coords editor is open, that location's marker can be dragged
        // (dragend fills the input; saving is still explicit).
        function setMarkerDraggable(number, enabled) {
            const marker = markers.find((m) => m.locationNumber === number);
            if (!marker) return;
            if (enabled) {
                marker.dragging.enable();
                marker.off("dragend");
                marker.on("dragend", () => {
                    const input = byId("cell-edit-input");
                    if (!input || !editing || editing.field !== "coords") return;
                    const ll = marker.getLatLng();
                    input.value = `${ll.lat}, ${ll.lng}`;
                });
            } else {
                marker.dragging.disable();
                marker.off("dragend");
            }
        }

        function cancelEdit() {
            if (!editing) return;
            const { number, field, originalHtml } = editing;
            const cell = byId(`cell-${field}-${number}`);
            if (cell) cell.innerHTML = originalHtml;
            if (field === "coords") setMarkerDraggable(number, false);
            editing = null;
            updateMapHint();
        }

        function startEdit(number, field) {
            if (editing && editing.number === number && editing.field === field) return;
            cancelEdit();

            const cell = byId(`cell-${field}-${number}`);
            if (!cell) return;

            editing = { number, field, originalHtml: cell.innerHTML };

            const current = field === "coords"
                ? `${cell.dataset.lat}, ${cell.dataset.lon}`
                : cell.textContent.replace("💣", "").trim();
            const inputType = field === "bombs" ? "number" : "text";
            const extra = field === "bombs"
                ? ' min="1" step="1"'
                : field === "coords"
                    ? ' style="width: 170px;"'
                    : ' maxlength="20" style="width: 110px; text-transform: uppercase;"';

            cell.innerHTML = `
                <span style="display: inline-flex; gap: 4px; align-items: center;">
                    <input class="cell-edit-input" type="${inputType}"${extra} id="cell-edit-input"
                           value="${current.replace(/"/g, "&quot;")}">
                    <button class="btn-save-cell">💾</button>
                    <button class="btn-cancel-cell">✕</button>
                </span>`;

            const input = byId("cell-edit-input");
            input.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") { ev.preventDefault(); saveEdit(); }
                else if (ev.key === "Escape") { ev.preventDefault(); cancelEdit(); }
            });
            input.focus();
            input.select();

            if (field === "coords") setMarkerDraggable(number, true);
            updateMapHint();
        }

        async function saveEdit() {
            if (!editing) return;
            const { number, field } = editing;
            const input = byId("cell-edit-input");
            if (!input) return;

            let value;
            if (field === "code") {
                const code = input.value.trim().toUpperCase();
                if (!code && codeRequired) { showToast("Code cannot be empty!", "error"); return; }
                if (code.length > 20) { showToast("Code must be 20 characters or fewer!", "error"); return; }
                if (code && !/^[A-Z0-9]+$/.test(code)) { showToast("Code may only contain letters and digits!", "error"); return; }
                value = code;
            } else if (field === "coords") {
                const parts = input.value.split(",");
                const lat = parts.length === 2 ? parseFloat(parts[0]) : NaN;
                const lon = parts.length === 2 ? parseFloat(parts[1]) : NaN;
                if (!isFinite(lat) || !isFinite(lon)) { showToast('Enter coordinates as "latitude, longitude"!', "error"); return; }
                if (lat < -90 || lat > 90) { showToast("Latitude must be between -90 and 90!", "error"); return; }
                if (lon < -180 || lon > 180) { showToast("Longitude must be between -180 and 180!", "error"); return; }
                value = { latitude: lat, longitude: lon };
            } else {
                const bombs = parseInt(input.value, 10);
                if (isNaN(bombs) || bombs < 1) { showToast("Bomb count must be at least 1!", "error"); return; }
                value = bombs;
            }

            try {
                const data = await adapter.saveField(number, field, value);
                if (data && data.success) {
                    if (field === "coords") setMarkerDraggable(number, false);
                    editing = null;
                    updateMapHint();
                    showToast(data.message, "success");
                    await load();
                } else {
                    showToast((data && data.message) || "Error saving", "error");
                }
            } catch (e) {
                console.error("Error saving cell edit:", e);
                showToast("Error saving", "error");
            }
        }

        // Host action: add one or more locations, reloading on success.
        async function addLocations(opts) {
            let data;
            try {
                data = await adapter.add(opts);
            } catch (e) {
                console.error("Error adding location:", e);
                return { success: false, message: "Error adding location" };
            }
            if (data && data.success) await load();
            return data || { success: false, message: "Error adding location" };
        }

        async function removeLocation(number, code) {
            const codeNote = code ? ` (code: ${code})` : "";
            if (!confirm(`Remove location ${number}${codeNote}?`)) return;
            try {
                const data = await adapter.remove(number);
                if (data && data.success) {
                    alert(data.message);
                    await load();
                } else {
                    alert("Error: " + ((data && data.message) || "unknown"));
                }
            } catch (e) {
                console.error("Error removing location:", e);
                alert("Error removing location");
            }
        }

        async function clearAll() {
            if (!confirm("Clear ALL locations? This cannot be undone!")) return;
            if (!confirm("Are you REALLY sure?")) return;
            try {
                const data = await adapter.clearAll();
                alert(data.message);
                if (data && data.success) await load();
            } catch (e) {
                console.error("Error clearing locations:", e);
                alert("Error clearing locations");
            }
        }

        // Drop a single location at the device's current GPS position (one tap).
        // count=1 + radius_km=0 so the pin lands exactly where we are.
        async function addAtMyLocation() {
            const btn = byId("btn-my-location");
            if (!btn || btn.disabled) return;

            // Browsers only expose the Geolocation API in secure contexts
            // (https:// or localhost) — a phone on http://LAN-IP gets neither.
            if (!window.isSecureContext || !navigator.geolocation) {
                showToast("GPS needs HTTPS — open this page via https:// or localhost to use your location.", "error");
                return;
            }

            const originalLabel = btn.textContent;
            btn.disabled = true;
            btn.textContent = "📍 Locating…";

            const restore = () => {
                btn.disabled = false;
                btn.textContent = originalLabel;
            };

            navigator.geolocation.getCurrentPosition(
                async (pos) => {
                    try {
                        const data = await adapter.add({
                            latitude: pos.coords.latitude,
                            longitude: pos.coords.longitude,
                            count: 1,
                            radiusKm: 0,
                        });
                        if (data && data.success) {
                            const accuracy = Math.round(pos.coords.accuracy || 0);
                            showToast(`📍 ${data.message} GPS ±${accuracy}m`, "success");
                            await load();
                        } else {
                            showToast((data && data.message) || "Error adding location", "error");
                        }
                    } catch (e) {
                        console.error("Error adding location at GPS position:", e);
                        showToast("Error adding location", "error");
                    } finally {
                        restore();
                    }
                },
                (err) => {
                    restore();
                    const msg = err.code === 1
                        ? "Location permission denied — allow it in your browser settings and try again."
                        : err.code === 2
                            ? "Couldn't determine your location (position unavailable)."
                            : "Timed out waiting for your location — try again.";
                    showToast(msg, "error");
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );
        }

        async function openQuizModal(number) {
            quizNumber = number;
            byId(els.quizTitle).textContent = `Location ${number} — Quiz`;
            byId(els.quizMode).value = "code";
            quizEditor.setQuestions([]);
            byId(els.quizModal).style.display = "flex";
            onQuizOpen(number);

            try {
                const data = await adapter.loadQuiz(number);
                if (data && data.success) {
                    byId(els.quizMode).value = data.mode || "code";
                    quizEditor.setQuestions(data.questions || []);
                } else if (data && data.message) {
                    showToast(data.message, "error");
                }
            } catch (e) {
                console.error("Error loading location quiz:", e);
                showToast("Error loading quiz", "error");
            }
        }

        function closeQuizModal() {
            byId(els.quizModal).style.display = "none";
            quizNumber = null;
        }

        async function saveQuiz(options = {}) {
            if (quizNumber === null) return false;
            const mode = byId(els.quizMode).value;
            const questions = quizEditor.getQuestions();

            // Every question must be able to yield at least 1 bomb (the server
            // enforces the same rule; this just gives an inline warning first).
            const badIdx = questions.findIndex(
                (q) => !q.answers || q.answers.length === 0 || quizEditor.questionMaxYield(q) < 1
            );
            if (badIdx !== -1) {
                quizEditor.updateWarnings();
                showToast(`Question ${badIdx + 1} has no answer worth at least 1 bomb.`, "error");
                return false;
            }

            try {
                const data = await adapter.saveQuiz(quizNumber, mode, questions);
                if (!data || !data.success) {
                    showToast((data && data.message) || "Error saving quiz", "error");
                    return false;
                }
                showToast(data.message || "Quiz saved!", "success");
                if (options.close !== false) {
                    closeQuizModal();
                    await load();
                }
                return true;
            } catch (e) {
                console.error("Error saving location quiz:", e);
                showToast("Error saving quiz", "error");
                return false;
            }
        }

        // Zoom the map to the current pins (used once by the set editor to
        // frame a saved layout instead of always opening on the default view).
        function fitBoundsToMarkers() {
            if (!map || markers.length === 0) return;
            map.fitBounds(L.latLngBounds(markers.map((m) => m.getLatLng())), {
                padding: [30, 30],
                maxZoom: 15,
            });
        }

        // Cell/button clicks are delegated, so re-rendering the table never
        // leaves stale inline handlers behind.
        const tbody = byId(els.tbody);
        if (tbody) {
            tbody.addEventListener("click", (ev) => {
                const target = ev.target;
                if (target.closest("button.btn-save-cell")) { ev.stopPropagation(); saveEdit(); return; }
                if (target.closest("button.btn-cancel-cell")) { ev.stopPropagation(); cancelEdit(); return; }
                const removeBtn = target.closest("[data-remove]");
                if (removeBtn) { removeLocation(Number(removeBtn.dataset.remove), removeBtn.dataset.code || null); return; }
                const quizCell = target.closest("[data-quiz]");
                if (quizCell) { openQuizModal(Number(quizCell.dataset.quiz)); return; }
                const editCell = target.closest("[data-edit]");
                if (editCell) { startEdit(Number(editCell.dataset.number), editCell.dataset.edit); return; }
            });
        }

        updateMapHint();

        return {
            load,
            addLocations,
            removeLocation,
            clearAll,
            addAtMyLocation,
            openQuizModal,
            closeQuizModal,
            saveQuiz,
            showToast,
            escapeHtml,
            quizEditor,
            fitBoundsToMarkers,
            get currentNumber() { return quizNumber; },
        };
    }

    window.createLocationEditor = createLocationEditor;
})();
