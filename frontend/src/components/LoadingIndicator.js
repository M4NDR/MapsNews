// src/components/LoadingIndicator.jsx
import React from 'react';
import '../styles/LoadingIndicator.css';

export default function LoadingIndicator({ text = "Загрузка..." }) {
  return (
    <div className="loading-indicator">
      <div className="spinner"></div>
      <p className="loading-text">{text}</p>
    </div>
  );
}