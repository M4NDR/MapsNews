import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/MiniNewsSidebar.css';

export default function MiniNewsSidebar({ news }) {
    const navigate = useNavigate();

    if (!news || news.length === 0) return null;

    return (
        <div className="mini-news-sidebar">
            <h3 className="sidebar-title">Последние новости</h3>
            <div className="mini-news-list">
                {news.map((item) => (
                    <div
                        key={item.id}
                        className="mini-news-card"
                        onClick={() => navigate(`/news/${item.id}`)}
                    >
                        <div className="mini-news-meta">
                            <span className="mini-news-date">{item.date}</span>
                            {item.views && (
                                <span className="mini-news-views">
                                    👁 {item.views}
                                </span>
                            )}
                        </div>
                        <h4 className="mini-news-title">{item.title}</h4>
                    </div>
                ))}
            </div>
        </div>
    );
}
