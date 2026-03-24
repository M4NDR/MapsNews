import React, { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import DetailPage from './pages/DetailPage';
import AdminModal from './components/AdminModal';
import useDarkMode from './hooks/useDarkMode';
import './styles/global.css';

function App() {
  useDarkMode(); // Инициализация темы глобально
  const [isAdminOpen, setIsAdminOpen] = useState(false);

  return (
    <>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/news/:id" element={<DetailPage />} />
      </Routes>
      
      {/* Кнопка админки видна всегда, открывает модальное окно */}
      <button 
        className="admin-modal-trigger"
        onClick={() => setIsAdminOpen(true)}
        title="Панель администратора"
      >
        Админ
      </button>

      {/* Само модальное окно */}
      <AdminModal 
        isOpen={isAdminOpen} 
        onClose={() => setIsAdminOpen(false)} 
      />
    </>
  );
}

export default App;