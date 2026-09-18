const providerSelect = document.getElementById("provider");
const modelSelect = document.getElementById("model");
const inferenceForm = document.getElementById("inference-form");
const resultSection = document.getElementById("result-section");
const formError = document.getElementById("form-error");

const systemPromptInput = document.getElementById("system-prompt");
const promptInput = document.getElementById("prompt");
const temperatureInput = document.getElementById("temperature");
const maxTokensInput = document.getElementById("max-tokens");

const submitButton = document.getElementById("submit-button");
const buttonText = document.getElementById("button-text");
const loadingIcon = document.getElementById("loading-icon");

const responseContent = document.getElementById("response-content");
const responseRequestedProvider = document.getElementById(
    "response-requested-provider"
);
const responseRequestedModel = document.getElementById(
    "response-requested-model"
);
const responseProvider = document.getElementById("response-provider");
const responseModel = document.getElementById("response-model");
const responsePromptTokens = document.getElementById(
    "response-prompt-tokens"
);
const responseCompletionTokens = document.getElementById(
    "response-completion-tokens"
);
const responseLatency = document.getElementById("response-latency");
const responseRequestId = document.getElementById("response-request-id");

const singleTab = document.getElementById("single-tab");
const batchTab = document.getElementById("batch-tab");
const singlePanel = document.getElementById("single-panel");
const batchPanel = document.getElementById("batch-panel");

const batchForm = document.getElementById("batch-form");
const batchRequestsContainer = document.getElementById("batch-requests");
const batchRequestTemplate = document.getElementById("batch-request-template");
const batchAddRequestButton = document.getElementById("batch-add-request");
const batchRequestCount = document.getElementById("batch-request-count");
const batchFormError = document.getElementById("batch-form-error");
const batchSubmitButton = document.getElementById("batch-submit-button");
const batchButtonText = document.getElementById("batch-button-text");
const batchLoadingIcon = document.getElementById("batch-loading-icon");

const batchResultSection = document.getElementById("batch-result-section");
const batchResultTotal = document.getElementById("batch-result-total");
const batchResultSuccess = document.getElementById("batch-result-success");
const batchResultFailures = document.getElementById("batch-result-failures");
const batchResultElapsed = document.getElementById("batch-result-elapsed");
const batchResultStatus = document.getElementById("batch-result-status");
const batchResultsList = document.getElementById("batch-results-list");

const API_BASE_URL =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
        ? "http://127.0.0.1:8000"
        : "https://api.thiagomemelli.com.br";

const API_URL = `${API_BASE_URL}/v1/inference`;
const BATCH_API_URL = `${API_BASE_URL}/v1/inference/batch`;

const MAX_BATCH_REQUESTS = 5;

const modelsByProvider = {
    groq: [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ],
    gemini: [
        "gemini-3.1-flash-lite",
    ],
};

const validationMessages = {
    provider: "Please select a provider.",
    model: "Please select a model.",
    prompt: "Please enter a prompt.",
    temperature: "Temperature must be between 0 and 2.",
    "max-tokens": "Max tokens must be an integer between 1 and 500.",
};


function populateModelOptions(provider, targetSelect) {
    targetSelect.innerHTML = "";

    if (!provider) {
        targetSelect.disabled = true;

        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Select a provider first";

        targetSelect.appendChild(option);
        return;
    }

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select a model";
    targetSelect.appendChild(defaultOption);

    for (const model of modelsByProvider[provider] || []) {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        targetSelect.appendChild(option);
    }

    targetSelect.disabled = false;
}


function updateModelOptions() {
    populateModelOptions(providerSelect.value, modelSelect);
}


function showFormError(message) {
    formError.textContent = message;
    formError.hidden = false;
}


function clearFormError() {
    formError.textContent = "";
    formError.hidden = true;
}


function showBatchFormError(message) {
    batchFormError.textContent = message;
    batchFormError.hidden = false;
}


function clearBatchFormError() {
    batchFormError.textContent = "";
    batchFormError.hidden = true;
}


function clearResponse() {
    resultSection.hidden = true;

    responseContent.textContent = "";
    responseRequestedProvider.textContent = "-";
    responseRequestedModel.textContent = "-";
    responseProvider.textContent = "-";
    responseModel.textContent = "-";
    responsePromptTokens.textContent = "-";
    responseCompletionTokens.textContent = "-";
    responseLatency.textContent = "-";
    responseRequestId.textContent = "-";
}


function clearBatchResponse() {
    batchResultSection.hidden = true;
    batchResultTotal.textContent = "-";
    batchResultSuccess.textContent = "-";
    batchResultFailures.textContent = "-";
    batchResultElapsed.textContent = "-";
    batchResultStatus.textContent = "Completed";
    batchResultStatus.className = "status-pill";
    batchResultsList.replaceChildren();
}


function getApiErrorMessage(response, data) {
    if (typeof data?.detail === "string") {
        return data.detail;
    }

    if (Array.isArray(data?.detail)) {
        return data.detail
            .map((error) => error.msg || "Invalid request.")
            .join(" ");
    }

    return `Request failed with status ${response.status}.`;
}


function switchMode(mode) {
    const isSingle = mode === "single";

    singlePanel.hidden = !isSingle;
    batchPanel.hidden = isSingle;

    singleTab.classList.toggle("active", isSingle);
    batchTab.classList.toggle("active", !isSingle);

    singleTab.setAttribute("aria-selected", String(isSingle));
    batchTab.setAttribute("aria-selected", String(!isSingle));

    if (isSingle) {
        clearBatchFormError();
        clearBatchResponse();
    } else {
        clearFormError();
        clearResponse();
    }
}


function resetSingleApplication() {
    inferenceForm.reset();
    providerSelect.value = "";
    updateModelOptions();
    clearFormError();
    clearResponse();

    submitButton.disabled = false;
    buttonText.textContent = "Run inference";
    loadingIcon.hidden = true;
}


function getBatchCards() {
    return Array.from(
        batchRequestsContainer.querySelectorAll(".batch-request-card")
    );
}


function configureBatchCard(card, index) {
    const requestNumber = index + 1;
    card.dataset.requestIndex = String(index);

    card.querySelector(".batch-request-number").textContent = String(requestNumber);

    const removeButton = card.querySelector(".batch-remove-request");
    removeButton.hidden = index === 0;

    const fieldConfig = [
        [".batch-provider", ".batch-provider-label", "provider"],
        [".batch-model", ".batch-model-label", "model"],
        [".batch-system-prompt", ".batch-system-prompt-label", "system-prompt"],
        [".batch-prompt", ".batch-prompt-label", "prompt"],
        [".batch-temperature", ".batch-temperature-label", "temperature"],
        [".batch-max-tokens", ".batch-max-tokens-label", "max-tokens"],
    ];

    for (const [fieldSelector, labelSelector, fieldName] of fieldConfig) {
        const field = card.querySelector(fieldSelector);
        const label = card.querySelector(labelSelector);
        const id = `batch-${fieldName}-${requestNumber}`;

        field.id = id;
        label.htmlFor = id;
    }
}


function updateBatchControls() {
    const cards = getBatchCards();

    cards.forEach((card, index) => configureBatchCard(card, index));

    batchRequestCount.textContent =
        `${cards.length} / ${MAX_BATCH_REQUESTS} requests`;

    batchAddRequestButton.hidden = cards.length >= MAX_BATCH_REQUESTS;
}


function attachBatchCardListeners(card) {
    const provider = card.querySelector(".batch-provider");
    const model = card.querySelector(".batch-model");
    const removeButton = card.querySelector(".batch-remove-request");

    provider.addEventListener("change", () => {
        populateModelOptions(provider.value, model);
        clearBatchFormError();
    });

    model.addEventListener("change", clearBatchFormError);

    for (const field of card.querySelectorAll("input, textarea")) {
        field.addEventListener("input", clearBatchFormError);
    }

    removeButton.addEventListener("click", () => {
        card.remove();
        updateBatchControls();
        clearBatchFormError();
        clearBatchResponse();
    });
}


function addBatchRequest() {
    const cards = getBatchCards();

    if (cards.length >= MAX_BATCH_REQUESTS) {
        return;
    }

    const fragment = batchRequestTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".batch-request-card");

    batchRequestsContainer.appendChild(fragment);
    attachBatchCardListeners(card);
    updateBatchControls();
}


function resetBatchApplication() {
    batchRequestsContainer.replaceChildren();
    clearBatchFormError();
    clearBatchResponse();

    batchSubmitButton.disabled = false;
    batchButtonText.textContent = "Run batch";
    batchLoadingIcon.hidden = true;

    addBatchRequest();
}


function getBatchValidationMessage(field, requestNumber) {
    const prefix = `Request ${requestNumber}: `;

    if (field.classList.contains("batch-provider")) {
        return `${prefix}Please select a provider.`;
    }

    if (field.classList.contains("batch-model")) {
        return `${prefix}Please select a model.`;
    }

    if (field.classList.contains("batch-prompt")) {
        return `${prefix}Please enter a prompt.`;
    }

    if (field.classList.contains("batch-temperature")) {
        if (field.validity.valueMissing) {
            return `${prefix}Please enter a temperature.`;
        }

        return `${prefix}Temperature must be a number between 0 and 2 with at most one decimal place.`;
    }

    if (field.classList.contains("batch-max-tokens")) {
        if (field.validity.valueMissing) {
            return `${prefix}Please enter the maximum number of tokens.`;
        }

        return `${prefix}Max tokens must be a whole number between 1 and 500.`;
    }

    return `${prefix}Please check this field.`;
}


function buildBatchPayload() {
    const requests = getBatchCards().map((card) => {
        const systemPrompt = card.querySelector(".batch-system-prompt").value.trim();

        return {
            provider: card.querySelector(".batch-provider").value,
            model: card.querySelector(".batch-model").value,
            prompt: card.querySelector(".batch-prompt").value.trim(),
            system_prompt: systemPrompt || null,
            temperature: Number(card.querySelector(".batch-temperature").value),
            max_tokens: Number(card.querySelector(".batch-max-tokens").value),
        };
    });

    return { requests };
}


function appendResultMeta(container, label, value) {
    const row = document.createElement("div");
    row.className = "batch-result-meta-row";

    const key = document.createElement("span");
    key.textContent = label;

    const content = document.createElement("strong");
    content.textContent = value ?? "-";

    row.append(key, content);
    container.appendChild(row);
}


function renderBatchResultItem(item, requestedItem, index) {
    const card = document.createElement("article");
    card.className = `batch-result-item ${item.success ? "success" : "failure"}`;

    const header = document.createElement("div");
    header.className = "batch-result-item-header";

    const title = document.createElement("h3");
    title.textContent = `Request ${index + 1}`;

    const state = document.createElement("span");
    state.className = `result-state ${item.success ? "success" : "failure"}`;
    state.textContent = item.success ? "Success" : "Failed";

    header.append(title, state);
    card.appendChild(header);

    const metadata = document.createElement("div");
    metadata.className = "batch-result-metadata";

    appendResultMeta(metadata, "Requested Provider", requestedItem.provider);
    appendResultMeta(metadata, "Requested Model", requestedItem.model);

    if (item.success && item.response) {
        appendResultMeta(metadata, "Executed Provider", item.response.provider);
        appendResultMeta(metadata, "Executed Model", item.response.model);
        appendResultMeta(metadata, "Prompt tokens", String(item.response.prompt_tokens));
        appendResultMeta(
            metadata,
            "Completion tokens",
            String(item.response.completion_tokens)
        );
        appendResultMeta(
            metadata,
            "Latency",
            `${Number(item.response.latency_ms).toFixed(2)} ms`
        );
    }

    appendResultMeta(metadata, "Request ID", item.request_id);
    card.appendChild(metadata);

    const requestContext = document.createElement("div");
    requestContext.className = "batch-request-context";

    const systemPromptLabel = document.createElement("span");
    systemPromptLabel.textContent = "System prompt";

    const systemPromptValue = document.createElement("pre");
    systemPromptValue.textContent =
        requestedItem.system_prompt || "Not provided";

    const promptLabel = document.createElement("span");
    promptLabel.textContent = "Prompt";

    const promptValue = document.createElement("pre");
    promptValue.textContent = requestedItem.prompt;

    requestContext.append(
        systemPromptLabel,
        systemPromptValue,
        promptLabel,
        promptValue
    );

    card.appendChild(requestContext);

    const content = document.createElement("pre");
    content.className = "batch-result-content";

    if (item.success && item.response) {
        content.textContent = item.response.content;
    } else {
        const errorType = item.error_type || "InferenceError";
        const errorMessage = item.error_message || "The request failed.";
        content.textContent = `${errorType}: ${errorMessage}`;
    }

    card.appendChild(content);
    batchResultsList.appendChild(card);
}


function renderBatchResponse(data, payload) {
    batchResultTotal.textContent = String(data.total);
    batchResultSuccess.textContent = String(data.success_count);
    batchResultFailures.textContent = String(data.failure_count);
    batchResultElapsed.textContent = `${Number(data.elapsed_ms).toFixed(2)} ms`;

    if (data.failure_count > 0) {
        batchResultStatus.textContent = "Completed with failures";
        batchResultStatus.className = "status-pill warning";
    } else {
        batchResultStatus.textContent = "Completed";
        batchResultStatus.className = "status-pill success";
    }

    batchResultsList.replaceChildren();

    data.results.forEach((item, index) => {
        renderBatchResultItem(item, payload.requests[index], index);
    });

    batchResultSection.hidden = false;
}


inferenceForm.addEventListener(
    "invalid",
    (event) => {
        event.preventDefault();

        if (!formError.hidden) {
            return;
        }

        const field = event.target;

        let message =
            validationMessages[field.id] || "Please check this field.";

        if (field.id === "temperature") {
            if (field.validity.valueMissing) {
                message = "Please enter a temperature.";
            } else if (field.validity.patternMismatch) {
                message =
                    "Temperature must be a number between 0 and 2 with at most one decimal place.";
            }
        }

        if (field.id === "max-tokens") {
            if (field.validity.valueMissing) {
                message = "Please enter the maximum number of tokens.";
            } else if (field.validity.patternMismatch) {
                message =
                    "Max tokens must be a whole number between 1 and 500.";
            }
        }

        showFormError(message);
        field.focus();
    },
    true
);


batchForm.addEventListener(
    "invalid",
    (event) => {
        event.preventDefault();

        if (!batchFormError.hidden) {
            return;
        }

        const field = event.target;
        const card = field.closest(".batch-request-card");
        const requestNumber = Number(card.dataset.requestIndex) + 1;

        showBatchFormError(
            getBatchValidationMessage(field, requestNumber)
        );
        field.focus();
    },
    true
);


submitButton.addEventListener("click", clearFormError);
providerSelect.addEventListener("change", () => {
    updateModelOptions();
    clearFormError();
});
modelSelect.addEventListener("change", clearFormError);
promptInput.addEventListener("input", clearFormError);
temperatureInput.addEventListener("input", clearFormError);
maxTokensInput.addEventListener("input", clearFormError);

singleTab.addEventListener("click", () => switchMode("single"));
batchTab.addEventListener("click", () => switchMode("batch"));

batchAddRequestButton.addEventListener("click", () => {
    addBatchRequest();
    clearBatchFormError();
    clearBatchResponse();
});


window.addEventListener("pageshow", () => {
    resetSingleApplication();
    resetBatchApplication();
    switchMode("single");
});


inferenceForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    clearFormError();
    clearResponse();

    const systemPrompt = systemPromptInput.value.trim();
    const prompt = promptInput.value.trim();
    const temperature = Number(temperatureInput.value);
    const maxTokens = Number(maxTokensInput.value);

    const payload = {
        provider: providerSelect.value,
        model: modelSelect.value,
        prompt: prompt,
        system_prompt: systemPrompt || null,
        temperature: temperature,
        max_tokens: maxTokens,
    };

    submitButton.disabled = true;
    buttonText.textContent = "Running...";
    loadingIcon.hidden = false;

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(getApiErrorMessage(response, data));
        }

        responseContent.textContent = data.content;
        responseRequestedProvider.textContent = payload.provider;
        responseRequestedModel.textContent = payload.model;
        responseProvider.textContent = data.provider;
        responseModel.textContent = data.model;
        responsePromptTokens.textContent = data.prompt_tokens;
        responseCompletionTokens.textContent = data.completion_tokens;
        responseLatency.textContent = `${data.latency_ms.toFixed(2)} ms`;
        responseRequestId.textContent = data.request_id;

        resultSection.hidden = false;
    } catch (error) {
        responseContent.textContent = `Error: ${error.message}`;
        resultSection.hidden = false;
    } finally {
        submitButton.disabled = false;
        buttonText.textContent = "Run inference";
        loadingIcon.hidden = true;
    }
});


batchForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    clearBatchFormError();
    clearBatchResponse();

    const payload = buildBatchPayload();

    if (payload.requests.length > MAX_BATCH_REQUESTS) {
        showBatchFormError(
            `A batch can contain at most ${MAX_BATCH_REQUESTS} requests.`
        );
        return;
    }

    batchSubmitButton.disabled = true;
    batchAddRequestButton.disabled = true;
    batchButtonText.textContent = "Running batch...";
    batchLoadingIcon.hidden = false;

    for (const removeButton of batchRequestsContainer.querySelectorAll(
        ".batch-remove-request"
    )) {
        removeButton.disabled = true;
    }

    try {
        const response = await fetch(BATCH_API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(getApiErrorMessage(response, data));
        }

        renderBatchResponse(data, payload);
    } catch (error) {
        showBatchFormError(`Error: ${error.message}`);
    } finally {
        batchSubmitButton.disabled = false;
        batchAddRequestButton.disabled = false;
        batchButtonText.textContent = "Run batch";
        batchLoadingIcon.hidden = true;

        for (const removeButton of batchRequestsContainer.querySelectorAll(
            ".batch-remove-request"
        )) {
            removeButton.disabled = false;
        }
    }
});
