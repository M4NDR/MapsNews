// src/api/index.js
// Если задана переменная окружения (например через .env файл или при билде), используем её.
// Иначе по умолчанию localhost.
const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

export const fetchNews = async (limit = 200, category = null) => {
    let url = `${API_URL}/news?limit=${limit}`;
    if (category && category !== "все") url += `&category=${category}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch news");
    return await res.json();
};

export const fetchNewsDetail = async (id) => {
    const res = await fetch(`${API_URL}/news/${id}/full`);
    if (!res.ok) throw new Error("Failed to fetch news detail");
    return await res.json();
};
