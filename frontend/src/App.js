// src/App.js
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import DetailPage from './pages/DetailPage';
import useDarkMode from './hooks/useDarkMode';
import './styles/global.css';

function App() {
  useDarkMode(); // Инициализация темы глобально

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/news/:id" element={<DetailPage />} />
    </Routes>
  );
}

export default App;