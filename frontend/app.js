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

const API_URL = "https://api.thiagomemelli.com.br/v1/inference";

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


function updateModelOptions() {
    const provider = providerSelect.value;

    modelSelect.innerHTML = "";

    if (!provider) {
        modelSelect.disabled = true;

        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Select a provider first";

        modelSelect.appendChild(option);
        return;
    }

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select a model";

    modelSelect.appendChild(defaultOption);

    for (const model of modelsByProvider[provider]) {
        const option = document.createElement("option");

        option.value = model;
        option.textContent = model;

        modelSelect.appendChild(option);
    }

    modelSelect.disabled = false;
}


function showFormError(message) {
    formError.textContent = message;
    formError.hidden = false;
}


function clearFormError() {
    formError.textContent = "";
    formError.hidden = true;
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


function resetApplication() {
    inferenceForm.reset();

    providerSelect.value = "";

    updateModelOptions();
    clearFormError();
    clearResponse();

    submitButton.disabled = false;
    buttonText.textContent = "Run inference";
    loadingIcon.hidden = true;
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


submitButton.addEventListener("click", () => {
    clearFormError();
});


providerSelect.addEventListener("change", () => {
    updateModelOptions();
    clearFormError();
});


modelSelect.addEventListener("change", () => {
    clearFormError();
});


promptInput.addEventListener("input", () => {
    clearFormError();
});


temperatureInput.addEventListener("input", () => {
    clearFormError();
});


maxTokensInput.addEventListener("input", () => {
    clearFormError();
});


window.addEventListener("pageshow", () => {
    resetApplication();
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
            let errorMessage =
                `Request failed with status ${response.status}.`;

            if (typeof data.detail === "string") {
                errorMessage = data.detail;
            } else if (Array.isArray(data.detail)) {
                errorMessage = data.detail
                    .map((error) => error.msg || "Invalid request.")
                    .join(" ");
            }

            throw new Error(errorMessage);
        }

        responseContent.textContent = data.content;
        responseRequestedProvider.textContent = payload.provider;
        responseRequestedModel.textContent = payload.model;
        responseProvider.textContent = data.provider;
        responseModel.textContent = data.model;
        responsePromptTokens.textContent = data.prompt_tokens;
        responseCompletionTokens.textContent = data.completion_tokens;
        responseLatency.textContent =
            `${data.latency_ms.toFixed(2)} ms`;
        responseRequestId.textContent = data.request_id;

        resultSection.hidden = false;
    } catch (error) {
        responseContent.textContent =
            `Error: ${error.message}`;

        resultSection.hidden = false;
    } finally {
        submitButton.disabled = false;
        buttonText.textContent = "Run inference";
        loadingIcon.hidden = true;
    }
});