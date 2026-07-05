'use client';

import { useState, useRef, useEffect } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Message {
  role: 'user' | 'agent';
  text: string;
  filters?: Record<string, any>;
}

interface Listing {
  id: string;
  source: string;
  source_url: string;
  property_type: string;
  deal_type: string;
  price: number;
  currency: string;
  area_m2: number | null;
  rooms: number | null;
  floor: number | null;
  floors_total: number | null;
  address: string;
  city: string;
  description: string | null;
  images: string[];
}

const PROPERTY_LABELS: Record<string, string> = {
  apartment: 'Квартира', house: 'Дом', commercial: 'Коммерция',
  land: 'Участок', room: 'Комната', studio: 'Студия',
};

const DEAL_LABELS: Record<string, string> = {
  sale: 'Продажа', rent: 'Аренда',
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'agent', text: '👋 Привет! Я AI-помощник по недвижимости.\n\nСпросите что угодно:\n• "2-комнатная квартира в Москве до 10 млн"\n• "сравни цены в Москве и Питере"\n• "аналитика по Краснодару"\n• "студия рядом с метро в аренду"' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [listings, setListings] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [view, setView] = useState<'chat' | 'listings'>('chat');
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', text }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      });
      const data = await res.json();

      setMessages(prev => [...prev, {
        role: 'agent',
        text: data.response || 'Не удалось обработать запрос',
        filters: data.filters,
      }]);

      if (data.total > 0) {
        // Fetch full listings for the cards
        const params = new URLSearchParams();
        if (data.filters?.city) params.set('city', data.filters.city);
        if (data.filters?.deal_type) params.set('deal_type', data.filters.deal_type);
        if (data.filters?.property_type) params.set('property_type', data.filters.property_type);
        if (data.filters?.price_min) params.set('price_min', String(data.filters.price_min));
        if (data.filters?.price_max) params.set('price_max', String(data.filters.price_max));
        if (data.filters?.rooms) params.set('rooms', String(data.filters.rooms));

        const listRes = await fetch(`${API}/api/listings?${params}`);
        const listData = await listRes.json();
        setListings(listData.items || []);
        setTotal(listData.total || 0);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'agent', text: '❌ Ошибка соединения с сервером' }]);
    }
    setLoading(false);
  };

  const formatPrice = (price: number) =>
    new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(price) + ' ₽';

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold text-primary-600">🏠 Realty AI</h1>
          <p className="text-xs text-gray-400 mt-1">Агрегатор недвижимости</p>
        </div>
        <nav className="flex-1 p-2">
          <button
            onClick={() => setView('chat')}
            className={`w-full text-left px-3 py-2 rounded-lg mb-1 ${view === 'chat' ? 'bg-primary-50 text-primary-700' : 'hover:bg-gray-100'}`}
          >
            💬 AI-Чат
          </button>
          <button
            onClick={() => setView('listings')}
            className={`w-full text-left px-3 py-2 rounded-lg mb-1 ${view === 'listings' ? 'bg-primary-50 text-primary-700' : 'hover:bg-gray-100'}`}
          >
            🏢 Объявления {total > 0 && <span className="text-xs bg-gray-200 px-2 py-0.5 rounded-full ml-1">{total}</span>}
          </button>
        </nav>
        <div className="p-4 border-t text-xs text-gray-400">
          MVP v0.1 • {total} объявлений
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col">
        {view === 'chat' ? (
          <>
            {/* Chat messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-2">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`chat-bubble ${msg.role}`}>
                    {msg.text}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="chat-bubble agent animate-pulse">⏳ Ищу...</div>
                </div>
              )}
              <div ref={chatEnd} />
            </div>

            {/* Input */}
            <div className="border-t bg-white p-4">
              <div className="flex gap-2 max-w-3xl mx-auto">
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendMessage()}
                  placeholder="Спросите о недвижимости..."
                  className="flex-1 border rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  disabled={loading}
                />
                <button
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  className="bg-primary-600 text-white px-6 py-3 rounded-xl hover:bg-primary-700 disabled:opacity-50 transition"
                >
                  →
                </button>
              </div>
            </div>
          </>
        ) : (
          /* Listings view */
          <div className="flex-1 overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Объявления ({total})</h2>
            </div>
            {listings.length === 0 ? (
              <div className="text-center text-gray-400 mt-20">
                <p className="text-4xl mb-4">🏠</p>
                <p>Нет объявлений. Попросите AI-агента что-нибудь найти!</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {listings.map(item => (
                  <a key={item.id} href={item.source_url} target="_blank" rel="noopener" className="listing-card">
                    {/* Image placeholder */}
                    <div className="h-40 bg-gray-100 rounded-lg mb-3 flex items-center justify-center overflow-hidden">
                      {item.images?.[0] ? (
                        <img src={item.images[0]} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-4xl">🏢</span>
                      )}
                    </div>

                    <div className="price">{formatPrice(item.price)}</div>

                    <div className="meta">
                      {PROPERTY_LABELS[item.property_type] || item.property_type} • {DEAL_LABELS[item.deal_type] || item.deal_type}
                    </div>

                    <div className="mt-2 text-sm">
                      {item.rooms !== null && <span className="font-medium">{item.rooms === 0 ? 'Студия' : `${item.rooms}-комн.`}</span>}
                      {item.area_m2 && <span> • {item.area_m2} м²</span>}
                      {item.floor && <span> • этаж {item.floor}/{item.floors_total}</span>}
                    </div>

                    <div className="mt-2 text-sm text-gray-600">📍 {item.city}, {item.address}</div>

                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-xs bg-gray-100 px-2 py-1 rounded">{item.source}</span>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
