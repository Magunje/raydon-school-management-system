document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("js-ready");

    const showToast = (message, type = "info") => {
        const stack = document.querySelector("[data-toast-stack]");
        if (!stack) {
            return;
        }
        const toast = document.createElement("div");
        toast.className = `ui-alert ui-alert-${type}`;
        toast.innerHTML = `<i class="bi bi-info-circle" aria-hidden="true"></i><span></span>`;
        toast.querySelector("span").textContent = message;
        stack.appendChild(toast);
        window.setTimeout(() => toast.remove(), 5200);
    };

    document.querySelectorAll("[data-print]").forEach((button) => {
        button.addEventListener("click", () => window.print());
    });

    let pendingConfirmForm = null;
    const ensureConfirmModal = () => {
        let modal = document.getElementById("ui-confirm-modal");
        if (modal) {
            return modal;
        }
        modal = document.createElement("div");
        modal.className = "modal fade";
        modal.id = "ui-confirm-modal";
        modal.tabIndex = -1;
        modal.setAttribute("aria-labelledby", "ui-confirm-title");
        modal.setAttribute("aria-hidden", "true");
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2 class="modal-title fs-5" id="ui-confirm-title">Confirm action</h2>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body" data-confirm-body>Continue?</div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-danger" data-confirm-submit>Confirm</button>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modal);
        modal.querySelector("[data-confirm-submit]").addEventListener("click", () => {
            const form = pendingConfirmForm;
            pendingConfirmForm = null;
            bootstrap.Modal.getOrCreateInstance(modal).hide();
            form?.submit();
        });
        return modal;
    };

    document.querySelectorAll("form[data-confirm-form]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            pendingConfirmForm = form;
            const trigger = event.submitter || form.querySelector("[data-confirm-message]");
            const modal = ensureConfirmModal();
            modal.querySelector("[data-confirm-body]").textContent = trigger?.dataset.confirmMessage || "Continue?";
            bootstrap.Modal.getOrCreateInstance(modal).show();
        });
    });

    const sidebar = document.querySelector("[data-sidebar]");
    const sidebarStorageKey = "raydonSidebarCollapsed";
    const isWideLayout = () => window.innerWidth > 1180;
    let lastSidebarTrigger = null;
    const setSidebarCollapsed = (collapsed) => {
        document.body.classList.toggle("sidebar-collapsed", collapsed);
        try {
            if (collapsed) {
                window.localStorage.setItem(sidebarStorageKey, "1");
            } else {
                window.localStorage.removeItem(sidebarStorageKey);
            }
        } catch (error) {
            // Private browsing modes can block localStorage; the visual state still works for this page.
        }
    };

    try {
        if (window.localStorage.getItem(sidebarStorageKey) === "1") {
            document.body.classList.add("sidebar-collapsed");
        }
    } catch (error) {
        // Ignore storage read errors and keep the default visible navigation.
    }

    const openSidebar = (event) => {
        lastSidebarTrigger = event?.currentTarget || null;
        setSidebarCollapsed(false);
        document.body.classList.add("sidebar-open");
        window.requestAnimationFrame(() => {
            const focusTarget = sidebar?.querySelector("[data-sidebar-close], .sidebar-link, .nav-link, .logout-link");
            focusTarget?.focus({ preventScroll: true });
        });
    };
    const closeSidebar = () => {
        const wasOpen = document.body.classList.contains("sidebar-open");
        document.body.classList.remove("sidebar-open");
        if (wasOpen && lastSidebarTrigger && window.innerWidth <= 1180) {
            window.requestAnimationFrame(() => lastSidebarTrigger.focus({ preventScroll: true }));
        }
    };

    const restoreSidebar = (event) => {
        lastSidebarTrigger = event?.currentTarget || null;
        setSidebarCollapsed(false);
        if (!isWideLayout()) {
            openSidebar(event);
        } else {
            window.requestAnimationFrame(() => {
                sidebar?.querySelector(".sidebar-link, .sidebar-brand")?.focus({ preventScroll: true });
            });
        }
    };

    document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
        button.addEventListener("click", restoreSidebar);
    });

    document.querySelectorAll("[data-sidebar-close]").forEach((button) => {
        button.addEventListener("click", closeSidebar);
    });

    document.querySelectorAll(".app-sidebar .sidebar-link, .sidebar .nav-link, .sidebar .logout-link").forEach((link) => {
        link.addEventListener("click", () => {
            if (isWideLayout()) {
                setSidebarCollapsed(true);
                return;
            }
            closeSidebar();
        });
    });

    document.querySelectorAll(".sidebar .brand, .sidebar-brand").forEach((link) => {
        link.addEventListener("click", () => {
            if (!isWideLayout()) {
                closeSidebar();
            }
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeSidebar();
        }
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 1180) {
            closeSidebar();
        }
    });

    document.querySelectorAll("[data-smart-back]").forEach((button) => {
        button.addEventListener("click", () => {
            const fallback = button.dataset.backFallback || "/";
            const next = new URLSearchParams(window.location.search).get("next");
            if (next && next.startsWith("/") && !next.startsWith("//")) {
                window.location.assign(next);
                return;
            }

            if (document.referrer) {
                try {
                    const referrer = new URL(document.referrer);
                    if (referrer.origin === window.location.origin && referrer.href !== window.location.href && window.history.length > 1) {
                        window.history.back();
                        return;
                    }
                } catch (error) {
                    // Invalid referrers fall through to the safe fallback.
                }
            }

            window.location.assign(fallback);
        });
    });

    const portalUpdatesUrl = document.body.dataset.portalUpdatesUrl;
    if (portalUpdatesUrl) {
        let portalUpdateSince = Number(document.body.dataset.portalUpdateSince || 0);
        let portalUpdateVisible = false;
        const autoRefresh = document.body.dataset.portalAutoRefresh !== "false";
        const banner = document.querySelector("[data-portal-update-banner]");
        const bannerMessage = document.querySelector("[data-portal-update-message]");
        const refreshButton = document.querySelector("[data-portal-refresh]");

        const showPortalUpdate = (events) => {
            if (portalUpdateVisible) {
                return;
            }
            portalUpdateVisible = true;
            const latestEvent = events[events.length - 1] || {};
            const message = latestEvent.details || "Staff have updated your school record.";

            if (bannerMessage) {
                bannerMessage.textContent = message;
            }
            if (banner) {
                banner.hidden = false;
            }

            if (autoRefresh) {
                window.setTimeout(() => window.location.reload(), 1300);
            }
        };

        refreshButton?.addEventListener("click", () => window.location.reload());

        const pollPortalUpdates = async () => {
            try {
                const params = new URLSearchParams({ since: String(portalUpdateSince) });
                const response = await fetch(`${portalUpdatesUrl}?${params.toString()}`, {
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    return;
                }
                const data = await response.json();
                if (Number.isFinite(Number(data.latest_event_id))) {
                    portalUpdateSince = Number(data.latest_event_id);
                }
                if (data.has_updates && Array.isArray(data.events) && data.events.length) {
                    showPortalUpdate(data.events);
                }
            } catch (error) {
                // A missed poll is harmless; the next successful poll will catch up.
            }
        };

        window.setInterval(pollPortalUpdates, 3000);
    }

    const clearFieldError = (control) => {
        const field = control.closest(".field");
        if (field) {
            field.classList.remove("has-error");
            const message = field.querySelector("[data-field-error]");
            if (message) {
                message.hidden = true;
            }
        }
        control.setAttribute("aria-invalid", "false");
    };

    document.querySelectorAll("form[data-form-errors]").forEach((form) => {
        const firstInvalidControl = form.querySelector(
            "input[aria-invalid='true'], select[aria-invalid='true'], textarea[aria-invalid='true']",
        );
        if (firstInvalidControl) {
            window.requestAnimationFrame(() => {
                firstInvalidControl.focus({ preventScroll: true });
                firstInvalidControl.scrollIntoView({ behavior: "smooth", block: "center" });
            });
        }

        form.querySelectorAll("input[aria-invalid='true'], select[aria-invalid='true'], textarea[aria-invalid='true']").forEach((control) => {
            ["input", "change"].forEach((eventName) => {
                control.addEventListener(eventName, () => clearFieldError(control), { once: true });
            });
        });
    });

    const bindPupilSearchPicker = (form, options = {}) => {
        if (!form) {
            return null;
        }

        const admissionInput = form.querySelector("[name='admission_no']");
        const pupilQueryInput = form.querySelector("[name='pupil_query']");
        const searchResults = form.querySelector(".search-results");
        const searchUrl = form.dataset.searchUrl;
        let searchTimer = null;

        if (!admissionInput || !pupilQueryInput || !searchResults || !searchUrl) {
            return null;
        }

        const clearSuggestions = () => {
            searchResults.innerHTML = "";
            searchResults.hidden = true;
        };

        const choosePupil = (item) => {
            pupilQueryInput.value = item.name;
            admissionInput.value = item.admission_no;
            clearSuggestions();
            if (typeof options.onPick === "function") {
                options.onPick(item);
            }
        };

        const renderSuggestions = (items) => {
            if (!items.length) {
                clearSuggestions();
                return;
            }

            searchResults.innerHTML = "";
            items.forEach((item) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "search-option";
                const title = document.createElement("strong");
                title.textContent = item.name;
                const meta = document.createElement("span");
                meta.textContent = `${item.admission_no} | ${item.class_label || `${item.grade || ""}${item.class_stream || ""}`}`;
                button.appendChild(title);
                button.appendChild(meta);
                button.addEventListener("click", () => choosePupil(item));
                searchResults.appendChild(button);
            });
            searchResults.hidden = false;
        };

        const syncAdmissionFromQuery = () => {
            const query = pupilQueryInput.value.trim();
            if (!query) {
                admissionInput.value = "";
                return;
            }

            if (/\d/.test(query) || query.toUpperCase().startsWith("ADM")) {
                admissionInput.value = query;
                return;
            }

            if (!admissionInput.value) {
                admissionInput.value = "";
            }
        };

        const searchPupils = async () => {
            const query = pupilQueryInput.value.trim();
            if (!query) {
                clearSuggestions();
                if (typeof options.onEmptyQuery === "function") {
                    options.onEmptyQuery();
                }
                return;
            }

            try {
                const response = await fetch(`${searchUrl}?${new URLSearchParams({ q: query }).toString()}`);
                if (!response.ok) {
                    clearSuggestions();
                    return;
                }

                const data = await response.json();
                renderSuggestions(data.items || []);
            } catch (error) {
                clearSuggestions();
            }
        };

        const scheduleSearch = () => {
            syncAdmissionFromQuery();
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(searchPupils, 180);
            if (typeof options.onInput === "function") {
                options.onInput();
            }
        };

        pupilQueryInput.addEventListener("input", scheduleSearch);
        pupilQueryInput.addEventListener("focus", () => {
            if (pupilQueryInput.value.trim()) {
                searchPupils();
            }
        });
        document.addEventListener("click", (event) => {
            if (!form.contains(event.target)) {
                clearSuggestions();
            }
        });

        return {
            admissionInput,
            pupilQueryInput,
            clearSuggestions,
            syncAdmissionFromQuery,
            searchPupils,
            choosePupil,
        };
    };

    const paymentForm = document.querySelector("[data-payment-form]");
    if (paymentForm) {
        const amountInput = paymentForm.querySelector("[name='amount_paid']");
        const paymentDateInput = paymentForm.querySelector("[name='payment_date']");
        const paymentDateManualInput = paymentForm.querySelector("[name='payment_date_manual']");
        const termInput = paymentForm.querySelector("[name='term']");
        const yearInput = paymentForm.querySelector("[name='year']");
        const lookupUrl = paymentForm.dataset.lookupUrl;
        let paymentDateTouched = false;
        const display = {
            name: document.getElementById("lookup-name"),
            pickedName: document.getElementById("lookup-picked-name"),
            pickedAdmission: document.getElementById("lookup-picked-admission"),
            pickedGrade: document.getElementById("lookup-picked-grade"),
            pickedStatus: document.getElementById("lookup-picked-status"),
            grade: document.getElementById("lookup-grade"),
            guardian: document.getElementById("lookup-guardian"),
            message: document.getElementById("lookup-message"),
            currentFees: document.getElementById("lookup-current-fees"),
            openingBalance: document.getElementById("lookup-opening-balance"),
            adjustments: document.getElementById("lookup-adjustments"),
            required: document.getElementById("lookup-required"),
            paid: document.getElementById("lookup-paid"),
            balance: document.getElementById("lookup-balance"),
            after: document.getElementById("lookup-after"),
            otherArrears: document.getElementById("lookup-other-arrears"),
            overallBalance: document.getElementById("lookup-overall-balance"),
            requiredTerm: document.getElementById("lookup-required-term"),
            advanceTerm: document.getElementById("lookup-advance-term"),
            ruleNote: document.getElementById("lookup-rule-note"),
            outstandingPanel: document.getElementById("lookup-outstanding-panel"),
            outstandingRows: document.getElementById("lookup-outstanding-rows"),
            allocationPanel: document.getElementById("lookup-allocation-panel"),
            allocationRows: document.getElementById("lookup-allocation-rows"),
            historyPanel: document.getElementById("lookup-history-panel"),
            historyRows: document.getElementById("lookup-history-rows"),
        };
        const money = (value) => new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
        }).format(Number(value || 0));
        let lastAllocatableBalance = 0;
        let currentOutstandingTerms = [];
        let currentAdvanceTerm = null;
        let lookupTimer = null;

        const picker = bindPupilSearchPicker(paymentForm, {
            onInput: () => scheduleLookup(),
            onPick: () => lookupPupil(),
            onEmptyQuery: () => resetLookup(""),
        });
        paymentForm.addEventListener("submit", () => {
            picker?.syncAdmissionFromQuery();
        });

        const currentLocalDate = () => {
            const now = new Date();
            const offset = now.getTimezoneOffset() * 60000;
            return new Date(now.getTime() - offset).toISOString().slice(0, 10);
        };

        if (paymentDateInput) {
            if (!paymentDateInput.value) {
                paymentDateInput.value = currentLocalDate();
            }
            if (paymentDateManualInput && !paymentDateManualInput.value) {
                paymentDateManualInput.value = "0";
            }
            ["input", "change"].forEach((eventName) => {
                paymentDateInput.addEventListener(eventName, () => {
                    paymentDateTouched = true;
                    if (paymentDateManualInput) {
                        paymentDateManualInput.value = "1";
                    }
                });
            });
            paymentForm.addEventListener("submit", () => {
                if (!paymentDateTouched) {
                    paymentDateInput.value = currentLocalDate();
                }
                if (paymentDateManualInput && !paymentDateTouched) {
                    paymentDateManualInput.value = "0";
                }
            });
        }

        const updateAfterPayment = () => {
            const amount = Number(amountInput.value || 0);
            display.after.textContent = money(lastAllocatableBalance - amount);
            if ((!currentOutstandingTerms.length && !currentAdvanceTerm) || amount <= 0) {
                display.allocationRows.innerHTML = "";
                display.allocationPanel.hidden = true;
                return;
            }

            let remaining = amount;
            display.allocationRows.innerHTML = "";
            currentOutstandingTerms.forEach((item) => {
                if (remaining <= 0) {
                    return;
                }
                const allocated = Math.min(Number(item.balance || 0), remaining);
                if (allocated <= 0) {
                    return;
                }
                const row = document.createElement("tr");
                const labelCell = document.createElement("td");
                labelCell.textContent = item.label;
                const amountCell = document.createElement("td");
                amountCell.className = "number";
                amountCell.textContent = money(allocated);
                row.appendChild(labelCell);
                row.appendChild(amountCell);
                display.allocationRows.appendChild(row);
                remaining -= allocated;
            });
            if (currentAdvanceTerm && remaining > 0) {
                const allocated = Math.min(Number(currentAdvanceTerm.balance || 0), remaining);
                if (allocated > 0) {
                    const row = document.createElement("tr");
                    const labelCell = document.createElement("td");
                    labelCell.textContent = `${currentAdvanceTerm.label} (advance)`;
                    const amountCell = document.createElement("td");
                    amountCell.className = "number";
                    amountCell.textContent = money(allocated);
                    row.appendChild(labelCell);
                    row.appendChild(amountCell);
                    display.allocationRows.appendChild(row);
                    remaining -= allocated;
                }
            }
            display.allocationPanel.hidden = display.allocationRows.children.length === 0;
        };

        const resetLookup = (message) => {
            lastAllocatableBalance = 0;
            currentOutstandingTerms = [];
            currentAdvanceTerm = null;
            display.name.textContent = "-";
            display.pickedName.textContent = "-";
            display.pickedAdmission.textContent = "-";
            display.pickedGrade.textContent = "-";
            display.pickedStatus.textContent = "-";
            display.pickedStatus.className = "status-pill";
            display.grade.textContent = "-";
            if (display.guardian) {
                display.guardian.textContent = "-";
            }
            display.message.textContent = message;
            display.message.hidden = !message;
            display.currentFees.textContent = money(0);
            display.openingBalance.textContent = money(0);
            display.adjustments.textContent = money(0);
            display.required.textContent = money(0);
            display.paid.textContent = money(0);
            display.balance.textContent = money(0);
            display.after.textContent = money(0);
            display.otherArrears.textContent = money(0);
            display.overallBalance.textContent = money(0);
            display.requiredTerm.textContent = "-";
            display.advanceTerm.textContent = "-";
            display.ruleNote.textContent = "";
            display.outstandingRows.innerHTML = "";
            display.outstandingPanel.hidden = true;
            display.allocationRows.innerHTML = "";
            display.allocationPanel.hidden = true;
            if (display.historyRows) {
                display.historyRows.innerHTML = "";
            }
            if (display.historyPanel) {
                display.historyPanel.hidden = true;
            }
        };

        const lookupPupil = async () => {
            const admissionNo = picker?.admissionInput.value.trim();
            if (!admissionNo) {
                resetLookup("");
                return;
            }

            const params = new URLSearchParams({
                admission_no: admissionNo,
                term: termInput.value,
                year: yearInput.value,
            });

            try {
                const response = await fetch(`${lookupUrl}?${params.toString()}`);
                if (!response.ok) {
                    resetLookup("");
                    return;
                }

                const data = await response.json();
                currentOutstandingTerms = data.outstanding_terms || [];
                currentAdvanceTerm = data.advance_payment_term || null;
                lastAllocatableBalance = currentOutstandingTerms.reduce(
                    (total, item) => total + Number(item.balance || 0),
                    0,
                ) + Number(currentAdvanceTerm?.balance || 0);
                display.name.textContent = data.pupil.name;
                display.pickedName.textContent = data.pupil.name;
                display.pickedAdmission.textContent = data.pupil.admission_no;
                display.pickedGrade.textContent = data.pupil.class_label || `${data.pupil.grade || ""}${data.pupil.class_stream || ""}`;
                display.pickedStatus.textContent = data.pupil.status;
                display.pickedStatus.className = `status-pill ${String(data.pupil.status || "").toLowerCase()}`;
                display.grade.textContent = data.pupil.class_label || `${data.pupil.grade || ""}${data.pupil.class_stream || ""}`;
                if (display.guardian) {
                    display.guardian.textContent = data.pupil.guardian_name || "-";
                }
                display.message.textContent = "";
                display.message.hidden = true;
                display.currentFees.textContent = money(data.current_fees);
                display.openingBalance.textContent = money(data.opening_balance);
                display.adjustments.textContent = money(data.manual_adjustments);
                display.required.textContent = money(data.amount_required);
                display.paid.textContent = money(data.total_paid);
                display.balance.textContent = money(data.balance);
                display.otherArrears.textContent = money(data.other_terms_balance);
                display.overallBalance.textContent = money(data.overall_balance);
                display.requiredTerm.textContent = data.required_payment_term
                    ? `${data.required_payment_term.label} (${money(data.required_payment_term.balance)})`
                    : "-";
                display.advanceTerm.textContent = currentAdvanceTerm
                    ? `${currentAdvanceTerm.label} (${money(currentAdvanceTerm.balance)})`
                    : "-";
                display.ruleNote.textContent = "";
                if (currentOutstandingTerms.length) {
                    display.outstandingRows.innerHTML = "";
                    currentOutstandingTerms.forEach((item) => {
                        const row = document.createElement("tr");
                        const labelCell = document.createElement("td");
                        labelCell.textContent = item.label;
                        const balanceCell = document.createElement("td");
                        balanceCell.className = "number";
                        balanceCell.textContent = money(item.balance);
                        row.appendChild(labelCell);
                        row.appendChild(balanceCell);
                        display.outstandingRows.appendChild(row);
                    });
                    display.outstandingPanel.hidden = false;
                } else {
                    display.outstandingRows.innerHTML = "";
                    display.outstandingPanel.hidden = true;
                }
                if (!picker.pupilQueryInput.value.trim()) {
                    picker.pupilQueryInput.value = data.pupil.name;
                }
                if (display.historyRows && display.historyPanel) {
                    display.historyRows.innerHTML = "";
                    (data.payment_history || []).forEach((item) => {
                        const row = document.createElement("tr");
                        const receiptCell = document.createElement("td");
                        receiptCell.textContent = item.receipt_no;
                        const dateCell = document.createElement("td");
                        dateCell.textContent = item.payment_date;
                        const amountCell = document.createElement("td");
                        amountCell.className = "number";
                        amountCell.textContent = money(item.amount_paid);
                        row.appendChild(receiptCell);
                        row.appendChild(dateCell);
                        row.appendChild(amountCell);
                        display.historyRows.appendChild(row);
                    });
                    display.historyPanel.hidden = display.historyRows.children.length === 0;
                }
                updateAfterPayment();
            } catch (error) {
                resetLookup("");
            }
        };

        const scheduleLookup = () => {
            window.clearTimeout(lookupTimer);
            lookupTimer = window.setTimeout(lookupPupil, 250);
        };

        [termInput, yearInput].forEach((input) => {
            input.addEventListener("input", scheduleLookup);
            input.addEventListener("change", scheduleLookup);
        });

        amountInput.addEventListener("input", updateAfterPayment);
        picker?.syncAdmissionFromQuery();
        lookupPupil();
    }

    const resultForm = document.querySelector("[data-result-form]");
    if (resultForm) {
        bindPupilSearchPicker(resultForm);
    }

    const posForm = document.querySelector("[data-pos-form]");
    if (posForm) {
        posForm.querySelectorAll("select[name^='item_id_']").forEach((select) => {
            const index = select.name.split("_").pop();
            const priceInput = posForm.querySelector(`[name='unit_price_${index}']`);
            const fillPrice = () => {
                const selectedOption = select.options[select.selectedIndex];
                if (priceInput && selectedOption?.dataset.price && !priceInput.value) {
                    priceInput.value = selectedOption.dataset.price;
                }
            };
            select.addEventListener("change", fillPrice);
            fillPrice();
        });
    }

    const offlineQueueKey = "raydonOfflineFormQueue";

    const offlineQueue = {
        read() {
            try {
                return JSON.parse(window.localStorage.getItem(offlineQueueKey) || "[]");
            } catch (error) {
                return [];
            }
        },
        write(items) {
            window.localStorage.setItem(offlineQueueKey, JSON.stringify(items));
            document.body.dataset.offlineQueueCount = String(items.length);
        },
        add(item) {
            const items = offlineQueue.read();
            items.push(item);
            offlineQueue.write(items);
        },
    };

    const formHasFiles = (formData) => {
        for (const value of formData.values()) {
            if (value instanceof File && value.name) {
                return true;
            }
        }
        return false;
    };

    const queueOfflineForm = (form) => {
        const formData = new FormData(form);
        if (formHasFiles(formData)) {
            return false;
        }
        offlineQueue.add({
            action: form.action || window.location.href,
            method: (form.method || "POST").toUpperCase(),
            body: new URLSearchParams(formData).toString(),
            createdAt: new Date().toISOString(),
        });
        showToast("Saved offline. It will sync automatically when this device is back online.", "success");
        form.reset();
        return true;
    };

    const getCookie = (name) => {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    const flushOfflineQueue = async () => {
        if (!navigator.onLine) {
            return;
        }
        const items = offlineQueue.read();
        if (!items.length) {
            offlineQueue.write([]);
            return;
        }

        const remaining = [];
        for (const item of items) {
            try {
                const csrfToken = getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value;
                let finalBody = item.body;
                if (csrfToken && item.body) {
                    try {
                        const bodyParams = new URLSearchParams(item.body);
                        bodyParams.set('csrfmiddlewaretoken', csrfToken);
                        finalBody = bodyParams.toString();
                    } catch (e) {
                        // fallback
                    }
                }
                const response = await fetch(item.action, {
                    method: item.method || "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Offline-Replay": "1",
                        ...(csrfToken ? { "X-CSRFToken": csrfToken } : {})
                    },
                    body: finalBody,
                });
                if (!response.ok) {
                    remaining.push(item);
                }
            } catch (error) {
                remaining.push(item);
            }
        }
        offlineQueue.write(remaining);
    };

    document.querySelectorAll("form[data-offline-queue]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (navigator.onLine) {
                return;
            }
            if (queueOfflineForm(form)) {
                event.preventDefault();
            }
        });
    });

    offlineQueue.write(offlineQueue.read());
    window.addEventListener("online", flushOfflineQueue);
    flushOfflineQueue();

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/service-worker.js").catch(() => {});
    }
});
