import React, { useState } from 'react';
import '../styles/AdminModal.css';

const AdminModal = ({ isOpen, onClose }) => {
    const [password, setPassword] = useState('');
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [logs, setLogs] = useState([]);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    if (!isOpen) return null;

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const API_URL = "";
            const res = await fetch(`${API_URL}/admin/logs?password=${password}`);

            if (res.ok) {
                const data = await res.json();
                setLogs(data);
                setIsAuthenticated(true);
            } else {
                if (res.status === 403) {
                    setError('Неверный пароль');
                } else {
                    const text = await res.text();
                    setError(`Ошибка ${res.status}: ${text}`);
                }
            }
        } catch (err) {
            setError('Ошибка соединения с сервером');
        }
        setLoading(false);
    };

    const handleClose = () => {
        setIsAuthenticated(false);
        setPassword('');
        setError('');
        onClose();
    };

    return (
        <div className="admin-modal-overlay">
            <div className={`admin-modal-content ${isAuthenticated ? 'admin-modal-large' : 'admin-modal-small'}`}>

                <button className="admin-close-btn" onClick={handleClose}>×</button>

                {!isAuthenticated ? (
                    <div className="admin-login-box">
                        <h2>Админ-панель</h2>
                        <form onSubmit={handleLogin}>
                            <input
                                type="password"
                                placeholder="Пароль"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                autoFocus
                            />
                            <button type="submit" disabled={loading}>
                                {loading ? "Проверка..." : "Войти"}
                            </button>
                        </form>
                        {error && <p className="admin-error">{error}</p>}
                    </div>
                ) : (
                    <div className="admin-logs-view">
                        <div className="admin-header">
                            <h2>Журнал работы геокодера</h2>
                        </div>

                        <div className="admin-table-wrapper">
                            <table className="admin-table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Новость</th>
                                        <th>Время парсинга</th>
                                        <th>Статус геокодирования</th>
                                        <th>Найденный адрес</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {logs.map(log => (
                                        <tr key={log.id}>
                                            <td>{log.id}</td>
                                            <td className="admin-title-cell">{log.title}</td>
                                            <td>{log.parsed_at || "—"}</td>
                                            <td>{log.geocoded_at || "⏳ Ожидание"}</td>
                                            <td className={log.address === 'NOT_FOUND' ? "addr-error" : log.address ? "addr-success" : ""}>
                                                {log.address === 'NOT_FOUND' ? " Не найдено" :
                                                    log.address ? ` ${log.address}` : "—"}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AdminModal;
