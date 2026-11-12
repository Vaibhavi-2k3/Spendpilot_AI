
"use strict";

const API_BASE_URL = "http://127.0.0.1:8000";

const form = document.getElementById("shopping-form");
const searchButton = document.getElementById("search-button");
const statusSection = document.getElementById("status-section");
const resultsSection = document.getElementById("results-section");
const resultsSummary = document.getElementById("results-summary");
const productGrid = document.getElementById("product-grid");
const intentSection = document.getElementById("intent-section");
const aiComparisonSection = document.getElementById("ai-comparison-section");

function setStatus(message, type = "") {
    statusSection.textContent = message;
    statusSection.className = "status-section";

    if (type === "error" || type === "success") {
        statusSection.classList.add(type);
    }
}

function setLoading(isLoading) {
    searchButton.disabled = isLoading;
    searchButton.textContent = isLoading
        ? "Finding products..."
        : "Find Products";
}

async function apiRequest(path, options = {}) {
    let response;

    try {
        response = await fetch(`${API_BASE_URL}${path}`, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {})
            }
        });
    } catch {
        throw new Error(
            "Cannot connect to SpendPilot API. " +
            "Check that the FastAPI server is running."
        );
    }

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error(
            `The API returned an invalid response (${response.status}).`
        );
    }

    if (!response.ok) {
        let detail = data.detail;

        if (Array.isArray(detail)) {
            detail = detail
                .map(item => item.msg || "Invalid input")
                .join("; ");
        }

        throw new Error(
            typeof detail === "string"
                ? detail
                : `Request failed (${response.status}).`
        );
    }

    return data;
}

function formatPrice(price, currency) {
    const amount = Number(price);

    if (!Number.isFinite(amount)) {
        return "Price unavailable";
    }

    try {
        return new Intl.NumberFormat(
            currency === "INR" ? "en-IN" : "en-US",
            {
                style: "currency",
                currency,
                maximumFractionDigits: 2
            }
        ).format(amount);
    } catch {
        return `${currency} ${amount.toFixed(2)}`;
    }
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text !== undefined && text !== null) {
        element.textContent = String(text);
    }

    return element;
}

function createProductCard(product) {
    const card = createElement("article", "product-card");
    card.dataset.productId = product.product_id;

    const imageContainer = createElement(
        "div",
        "product-image"
    );

    if (
        typeof product.image_url === "string" &&
        /^https:\/\//i.test(product.image_url)
    ) {
        const image = document.createElement("img");
        image.src = product.image_url;
        image.alt = product.name;
        image.loading = "lazy";

        image.onerror = () => {
            image.remove();
            imageContainer.textContent = "No image available";
        };

        imageContainer.appendChild(image);
    } else {
        imageContainer.textContent = "No image available";
    }

    card.appendChild(imageContainer);

    const content = createElement(
        "div",
        "product-content"
    );

    content.appendChild(
        createElement(
            "span",
            "product-merchant",
            product.merchant
        )
    );

    content.appendChild(
        createElement(
            "h3",
            "product-title",
            product.name
        )
    );

    if (product.description) {
        content.appendChild(
            createElement(
                "p",
                "product-description",
                product.description
            )
        );
    }

    content.appendChild(
        createElement(
            "div",
            "product-price",
            formatPrice(product.price, product.currency)
        )
    );

    const score = Number(product.score);

    if (Number.isFinite(score)) {
        content.appendChild(
            createElement(
                "span",
                "product-score",
                `Ranking score: ${(score * 100).toFixed(1)}%`
            )
        );
    }

    if (product.reasoning) {
        content.appendChild(
            createElement(
                "p",
                "product-reasoning",
                product.reasoning
            )
        );
    }

    const isExternal =
        product.link_type === "shopping_discovery";

    const notice = isExternal
        ? "External shopping listing. Price and stock are not verified. Not eligible for PayPal sandbox checkout."
        : product.checkout_eligible
            ? "Demo product. Sandbox checkout integration is not yet available."
            : "Demo product. Checkout is currently unavailable.";

    content.appendChild(
        createElement("p", "product-notice", notice)
    );

    const productUrl = product.product_url;

    if (
        isExternal &&
        typeof productUrl === "string" &&
        /^https:\/\//i.test(productUrl)
    ) {
        const link = createElement(
            "a",
            "product-action",
            "View Shopping Listing"
        );

        link.href = productUrl;
        link.target = "_blank";
        link.rel = "noopener noreferrer";

        content.appendChild(link);
    } else {
        const label = createElement(
            "span",
            "product-action",
            "Demo Product — Checkout Coming Soon"
        );

        content.appendChild(label);
    }

    card.appendChild(content);

    return card;
}

function renderProducts(products, currency) {
    productGrid.replaceChildren();

    resultsSection.hidden = false;

    if (!Array.isArray(products) || products.length === 0) {
        resultsSummary.textContent =
            "No recommended products found.";

        setStatus(
            "No products matched your budget and search.",
            "error"
        );

        return;
    }

    resultsSummary.textContent =
        `${products.length} recommended product(s) · ${currency}`;

    const fragment = document.createDocumentFragment();

    for (const product of products) {
        fragment.appendChild(createProductCard(product));
    }

    productGrid.appendChild(fragment);

    setStatus(
        `Found ${products.length} recommended product(s).`,
        "success"
    );
}

function renderIntent(result) {
    intentSection.hidden = false;
    document.getElementById("intent-query").textContent =
        `Search: ${result.intent.search_query}`;
    const details = [];
    if (result.intent.use_case) {
        details.push(`Use case: ${result.intent.use_case}`);
    }
    if (result.intent.preferences.length > 0) {
        details.push(`Preferences: ${result.intent.preferences.join(" · ")}`);
    }
    document.getElementById("intent-details").textContent = details.join(" — ");
    document.getElementById("intent-status").textContent =
        result.provider === "gemini"
            ? "Interpreted by Gemini. Your entered budget and currency are preserved."
            : result.message;
}

function renderAIComparison(report) {
    aiComparisonSection.hidden = false;
    const isGemini = report.provider === "gemini" && report.status === "ready";
    document.getElementById("ai-comparison-heading").textContent = isGemini
        ? `Gemini comparison · top ${report.products.length} options`
        : "Rule-based comparison";
    document.getElementById("ai-comparison-summary").textContent = report.summary;
    document.getElementById("ai-comparison-status").textContent = report.message ||
        "Explanations cite the supplied listing text. Prices, stock status, and checkout eligibility remain catalog-controlled.";

    if (!isGemini) {
        return;
    }

    const cards = new Map(
        Array.from(productGrid.querySelectorAll(".product-card"))
            .map(card => [card.dataset.productId, card])
    );
    for (const product of report.products) {
        const card = cards.get(product.product_id);
        if (!card) {
            continue;
        }
        const content = card.querySelector(".product-content");
        if (product.product_id === report.recommended_product_id) {
            card.classList.add("ai-recommended");
            content.prepend(createElement("span", "ai-pick", "Gemini's suggested pick"));
        }

        const explanation = createElement("section", "ai-explanation");
        explanation.appendChild(createElement("h4", "", "Why it fits"));
        explanation.appendChild(createElement("p", "", product.explanation));
        const evidenceList = createElement("ul", "ai-evidence");
        for (const evidence of product.evidence) {
            evidenceList.appendChild(createElement(
                "li", "", `Listing ${evidence.field}: “${evidence.quote}”`
            ));
        }
        explanation.appendChild(evidenceList);
        content.insertBefore(explanation, content.querySelector(".product-notice"));
    }
}

async function handleShoppingSearch(event) {
    event.preventDefault();

    const query = document.getElementById("query")
        .value.trim();

    const budget = Number(
        document.getElementById("budget").value
    );

    const currency = document.getElementById("currency")
        .value;

    const source = document.getElementById("source")
        .value;

    if (!query) {
        setStatus("Enter a product to search for.", "error");
        return;
    }

    if (
        !Number.isSafeInteger(budget) ||
        budget <= 0 ||
        budget > 2147483647
    ) {
        setStatus(
            "Enter a whole-number budget between 1 and 2,147,483,647.",
            "error"
        );
        return;
    }

    if (source === "demo" && currency !== "USD") {
        setStatus(
            "The demo catalog currently supports USD only. " +
            "Choose USD or switch to Live Shopping Search.",
            "error"
        );
        return;
    }

    setLoading(true);
    resultsSection.hidden = true;
    intentSection.hidden = true;
    aiComparisonSection.hidden = true;
    productGrid.replaceChildren();

    try {
        setStatus("Creating your shopping session...");

        const session = await apiRequest(
            "/api/shopping-sessions",
            {
                method: "POST",
                body: JSON.stringify({
                    query,
                    budget_amount: budget,
                    currency
                })
            }
        );

        const sessionId = session.id;

        if (!sessionId) {
            throw new Error(
                "Shopping session response is missing its ID."
            );
        }

        setStatus("Understanding your shopping request...");
        try {
            const intent = await apiRequest(
                `/api/shopping-sessions/${encodeURIComponent(sessionId)}/intent`,
                { method: "POST" }
            );
            renderIntent(intent);
        } catch {
            renderIntent({
                provider: "rule_based",
                intent: { search_query: query, use_case: null, preferences: [] },
                message: "Intent analysis is unavailable. Using your original search request."
            });
        }

        setStatus("Discovering products...");

        await apiRequest(
            `/api/shopping-sessions/${encodeURIComponent(sessionId)}/discover?source=${encodeURIComponent(source)}`,
            { method: "POST" }
        );

        setStatus("Generating recommendations...");

        await apiRequest(
            `/api/shopping-sessions/${encodeURIComponent(sessionId)}/recommendations`,
            { method: "POST" }
        );

        setStatus("Preparing product comparison...");

        const comparison = await apiRequest(
            `/api/shopping-sessions/${encodeURIComponent(sessionId)}/comparison`
        );

        renderProducts(comparison, currency);

        if (Array.isArray(comparison) && comparison.length > 0) {
            setStatus("Products found. Preparing your AI comparison...");
            try {
                const report = await apiRequest(
                    `/api/shopping-sessions/${encodeURIComponent(sessionId)}/ai-comparison`,
                    { method: "POST" }
                );
                renderAIComparison(report);
            } catch {
                renderAIComparison({
                    provider: "rule_based", status: "unavailable", products: [],
                    summary: "Products are ordered by relevance and budget efficiency.",
                    message: "AI comparison is unavailable. Your product results are still available."
                });
            }
            setStatus(`Found ${comparison.length} recommended product(s).`, "success");
        }
    } catch (error) {
        setStatus(
            error instanceof Error
                ? error.message
                : "An unexpected error occurred.",
            "error"
        );
    } finally {
        setLoading(false);
    }
}

form.addEventListener("submit", handleShoppingSearch);
