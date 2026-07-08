'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import dynamic from 'next/dynamic';

const MapView = dynamic(() => import('../components/MapView'), { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/* ═══ Types ═══════════════════════════════════════════════════ */

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
  district: string | null;
  region: string | null;
  description: string | null;
  images: string[];
  lat: number | null;
  lon: number | null;
  features: Record<string, any>;
  created_at: string;
}

interface Filters {
  city: string;
  deal_type: string;
  property_type: string;
  rooms: string;
  price_min: string;
  price_max: string;
}

/* ═══ Constants ═══════════════════════════════════════════════ */

const PROPERTY_LABELS: Record<string, string> = {
  apartment: 'Квартира', house: 'Дом', commercial: 'Коммерция',
  land: 'Участок', room: 'Комната', studio: 'Студия',
};

const DEAL_LABELS: Record<string, string> = {
  sale: 'Продажа', rent: 'Аренда',
};

const CITIES = [
  'Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург',
  'Казань', 'Краснодар', 'Сочи', 'Самара', 'Уфа', 'Владивосток',
];

const SUGGESTIONS = [
  '2-комнатная квартира в Москве до 10 млн',
  'Студия в Санкт-Петербурге в аренду',
  'Сравни цены в Москве и Питере',
  'Аналитика по Краснодару',
  'Сколько объявлений на платформе?',
  'Дом в Сочи до 15 млн',
];

/* ═══ Helpers ═════════════════════════════════════════════════ */

function formatPrice(price: number, dealType?: string): string {
  if (dealType === 'rent') {
    return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(price) + ' ₽/мес';
  }
  if (price >= 1_000_000) {
    const mln = price / 1_000_000;
    return mln % 1 === 0 ? `${mln} млн ₽` : `${mln.toFixed(1)} млн ₽`;
  }
  if (price >= 1_000) {
    return (price / 1_000).toFixed(0) + ' тыс ₽';
  }
  return price + ' ₽';
}

/* ═══ Skeleton ════════════════════════════════════════════════ */

function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 animate-pulse">
      <div className="h-40 bg-gray-200 rounded-lg mb-3" />
      <div className="h-6 bg-gray-200 rounded w-1/2 mb-2" />
      <div className="h-4 bg-gray-100 rounded w-1/3 mb-2" />
      <div className="h-4 bg-gray-100 rounded w-2/3 mb-2" />
      <div className="h-4 bg-gray-100 rounded w-full" />
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {[1, 2, 3, 4, 5, 6].map(i => <CardSkeleton key={i} />)}
    </div>
  );
}

/* ═══ Detail View ═════════════════════════════════════════════ */

function DetailView({ listing, onBack }: { listing: Listing; onBack: () => void }) {
  const [imgIdx, setImgIdx] = useState(0);
  const images = listing.images?.length ? listing.images : [];

  return (
    <div className="min-h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-4">
          <button onClick={onBack} className="text-blue-600 hover:text-blue-800 text-sm font-medium">
            ← Назад
          </button>
          <h1 className="text-lg font-semibold truncate">
            {PROPERTY_LABELS[listing.property_type]} • {listing.city}
          </h1>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left */}
          <div className="lg:col-span-2 space-y-6">
            {/* Images */}
            {images.length > 0 ? (
              <div>
                <div className="aspect-video bg-gray-100 rounded-xl overflow-hidden">
                  <img src={images[imgIdx]} alt="" className="w-full h-full object-cover" />
                </div>
                {images.length > 1 && (
                  <div className="flex gap-2 mt-3 overflow-x-auto pb-2">
                    {images.map((img, i) => (
                      <button key={i} onClick={() => setImgIdx(i)}
                        className={`flex-shrink-0 w-20 h-16 rounded-lg overflow-hidden border-2 transition ${i === imgIdx ? 'border-blue-500' : 'border-transparent'}`}>
                        <img src={img} alt="" className="w-full h-full object-cover" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="aspect-video bg-gray-100 rounded-xl flex items-center justify-center">
                <span className="text-6xl">🏢</span>
              </div>
            )}

            {/* Description */}
            {listing.description && (
              <div className="bg-white rounded-xl border p-6">
                <h2 className="font-semibold mb-3">Описание</h2>
                <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{listing.description}</p>
              </div>
            )}

            {/* Features */}
            {listing.features && Object.keys(listing.features).length > 0 && (
              <div className="bg-white rounded-xl border p-6">
                <h2 className="font-semibold mb-3">Характеристики</h2>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(listing.features).map(([k, v]) => (
                    <div key={k} className="text-sm">
                      <span className="text-gray-500">{k}:</span> <span className="font-medium">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Map */}
            {listing.lat && listing.lon && (
              <div className="bg-white rounded-xl border p-6">
                <h2 className="font-semibold mb-3">📍 На карте</h2>
                <div className="h-80 rounded-lg overflow-hidden">
                  <MapView lat={listing.lat} lon={listing.lon} address={`${listing.city}, ${listing.address}`} />
                </div>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-4">
            <div className="bg-white rounded-xl border p-6 sticky top-20">
              <div className="text-3xl font-bold text-blue-600 mb-1">
                {formatPrice(listing.price, listing.deal_type)}
              </div>
              <div className="text-sm text-gray-500 mb-4">
                {DEAL_LABELS[listing.deal_type]} • {PROPERTY_LABELS[listing.property_type]}
              </div>

              <div className="space-y-3 mb-6">
                {listing.rooms !== null && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Комнаты</span>
                    <span className="font-medium">{listing.rooms === 0 ? 'Студия' : listing.rooms}</span>
                  </div>
                )}
                {listing.area_m2 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Площадь</span>
                    <span className="font-medium">{listing.area_m2} м²</span>
                  </div>
                )}
                {listing.floor && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Этаж</span>
                    <span className="font-medium">{listing.floor}/{listing.floors_total}</span>
                  </div>
                )}
                {listing.area_m2 && listing.area_m2 > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Цена за м²</span>
                    <span className="font-medium">
                      {new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(listing.price / listing.area_m2)} ₽
                    </span>
                  </div>
                )}
              </div>

              <div className="border-t pt-4 mb-4">
                <div className="text-sm text-gray-700">📍 {listing.city}</div>
                <div className="text-sm text-gray-500 mt-1">{listing.address}</div>
                {listing.district && <div className="text-sm text-gray-400 mt-1">{listing.district}</div>}
              </div>

              <a href={listing.source_url} target="_blank" rel="noopener noreferrer"
                className="block w-full bg-blue-600 text-white text-center py-3 rounded-xl font-medium hover:bg-blue-700 transition">
                Смотреть на {listing.source} ↗
              </a>

              <p className="text-xs text-gray-400 mt-3 text-center">Источник: {listing.source}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══ Main Component ═════════════════════════════════════════ */

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'agent', text: '👋 Привет! Я AI-помощник по недвижимости.\n\nСпросите что угодно или выберите быстрый запрос:' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [listings, setListings] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [view, setView] = useState<'chat' | 'listings' | 'detail'>('chat');
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    city: '', deal_type: '', property_type: '', rooms: '', price_min: '', price_max: '',
  });
  const [showSkeleton, setShowSkeleton] = useState(false);
  const [coldStart, setColdStart] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);
  const coldStartTimer = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /* ── Cold start ───────────────────────────────────────── */
  const startColdTimer = useCallback(() => {
    setColdStart(false);
    coldStartTimer.current = setTimeout(() => setColdStart(true), 8000);
  }, []);

  const clearColdTimer = useCallback(() => {
    if (coldStartTimer.current) clearTimeout(coldStartTimer.current);
    setColdStart(false);
  }, []);

  /* ── Open detail ──────────────────────────────────────── */
  const openDetail = async (id: string) => {
    setDetailLoading(true);
    setView('detail');
    try {
      const res = await fetch(`${API}/api/listings/${id}`);
      if (!res.ok) throw new Error('Not found');
      const data = await res.json();
      setSelectedListing(data);
    } catch {
      setSelectedListing(null);
    }
    setDetailLoading(false);
  };

  /* ── Back from detail ─────────────────────────────────── */
  const backFromDetail = () => {
    setSelectedListing(null);
    setView(listings.length > 0 ? 'listings' : 'chat');
  };

  /* ── Send message ─────────────────────────────────────── */
  const sendMessage = async (text?: string) => {
    const query = (text || input).trim();
    if (!query || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: query }]);
    setLoading(true);
    setShowSkeleton(false);
    startColdTimer();

    try {
      const res = await fetch(`${API}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setMessages(prev => [...prev, {
        role: 'agent',
        text: data.response || 'Не удалось обработать запрос',
        filters: data.filters,
      }]);

      if (data.total > 0) {
        setShowSkeleton(true);
        const params = buildListingsParams(data.filters);
        const listRes = await fetch(`${API}/api/listings?${params}`);
        const listData = await listRes.json();
        setListings(listData.items || []);
        setTotal(listData.total || 0);
        setOffset(listData.items?.length || 0);
        setShowSkeleton(false);
        setView('listings');
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'agent',
        text: '❌ **Ошибка соединения**\n\nСервер не отвечает. Если вы на Render Free — первый запрос может занимать до 60 секунд (cold start). Попробуйте ещё раз.',
      }]);
      setShowSkeleton(false);
    }
    clearColdTimer();
    setLoading(false);
  };

  /* ── Load more ────────────────────────────────────────── */
  const loadMore = async () => {
    if (loadingMore || offset >= total) return;
    setLoadingMore(true);
    try {
      const params = buildListingsParams(getCurrentFilters());
      params.set('offset', String(offset));
      const res = await fetch(`${API}/api/listings?${params}`);
      const data = await res.json();
      setListings(prev => [...prev, ...(data.items || [])]);
      setOffset(prev => prev + (data.items?.length || 0));
    } catch { /* silent */ }
    setLoadingMore(false);
  };

  function getCurrentFilters(): Record<string, string> {
    return messages.filter(m => m.filters).pop()?.filters || {};
  }

  function buildListingsParams(f: Record<string, any> = {}): URLSearchParams {
    const p = new URLSearchParams();
    if (f.city) p.set('city', f.city);
    if (f.deal_type) p.set('deal_type', f.deal_type);
    if (f.property_type) p.set('property_type', f.property_type);
    if (f.price_min) p.set('price_min', String(f.price_min));
    if (f.price_max) p.set('price_max', String(f.price_max));
    if (f.rooms) p.set('rooms', String(f.rooms));
    return p;
  }

  /* ── Filter search ────────────────────────────────────── */
  const applyFilters = async () => {
    const parts: string[] = [];
    if (filters.city) parts.push(filters.city);
    if (filters.property_type) parts.push(PROPERTY_LABELS[filters.property_type] || filters.property_type);
    if (filters.deal_type) parts.push(filters.deal_type === 'rent' ? 'в аренду' : 'купить');
    if (filters.rooms) parts.push(`${filters.rooms}-комнатная`);
    if (filters.price_max) parts.push(`до ${Number(filters.price_max) / 1_000_000} млн`);
    if (parts.length === 0) return;
    await sendMessage(parts.join(' '));
    setSidebarOpen(false);
  };

  /* ═══ RENDER ════════════════════════════════════════════ */

  // Detail view
  if (view === 'detail') {
    return (
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar (hidden on detail) */}
        <aside className="hidden lg:flex w-72 bg-white border-r flex-col">
          <div className="p-4 border-b">
            <h1 className="text-xl font-bold text-blue-600">🏠 Realty AI</h1>
          </div>
          <div className="p-4 flex-1 flex items-center justify-center text-gray-400 text-sm">
            <button onClick={backFromDetail} className="text-blue-600 hover:underline">
              ← Вернуться к результатам
            </button>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-pulse text-gray-400">⏳ Загрузка объявления...</div>
            </div>
          ) : selectedListing ? (
            <DetailView listing={selectedListing} onBack={backFromDetail} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <p className="text-5xl">😕</p>
              <p className="text-gray-600">Объявление не найдено</p>
              <button onClick={backFromDetail} className="text-blue-600 hover:underline">← Назад</button>
            </div>
          )}
        </main>
      </div>
    );
  }

  // Main view (chat + listings)
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/30 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* ═══ Sidebar ═══════════════════════════════════════ */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-50 w-72 bg-white border-r border-gray-200
        flex flex-col transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-blue-600">🏠 Realty AI</h1>
            <p className="text-xs text-gray-400 mt-0.5">Агрегатор недвижимости</p>
          </div>
          <button className="lg:hidden p-1" onClick={() => setSidebarOpen(false)}>✕</button>
        </div>

        <nav className="p-2 space-y-1">
          <button onClick={() => { setView('chat'); setSidebarOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${view === 'chat' ? 'bg-blue-50 text-blue-700 font-medium' : 'hover:bg-gray-100'}`}>
            💬 AI-Чат
          </button>
          <button onClick={() => { setView('listings'); setSidebarOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${view === 'listings' ? 'bg-blue-50 text-blue-700 font-medium' : 'hover:bg-gray-100'}`}>
            🏢 Объявления {total > 0 && <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded-full ml-1">{total}</span>}
          </button>
        </nav>

        {/* Filters */}
        <div className="p-4 border-t flex-1 overflow-y-auto">
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Фильтры</h3>

          <label className="block text-xs text-gray-600 mb-1">Город</label>
          <select value={filters.city} onChange={e => setFilters(f => ({ ...f, city: e.target.value }))}
            className="w-full border rounded-lg px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-blue-500 focus:outline-none">
            <option value="">Все города</option>
            {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>

          <label className="block text-xs text-gray-600 mb-1">Тип сделки</label>
          <select value={filters.deal_type} onChange={e => setFilters(f => ({ ...f, deal_type: e.target.value }))}
            className="w-full border rounded-lg px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-blue-500 focus:outline-none">
            <option value="">Все</option>
            <option value="sale">Продажа</option>
            <option value="rent">Аренда</option>
          </select>

          <label className="block text-xs text-gray-600 mb-1">Тип недвижимости</label>
          <select value={filters.property_type} onChange={e => setFilters(f => ({ ...f, property_type: e.target.value }))}
            className="w-full border rounded-lg px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-blue-500 focus:outline-none">
            <option value="">Все</option>
            {Object.entries(PROPERTY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>

          <label className="block text-xs text-gray-600 mb-1">Комнаты</label>
          <select value={filters.rooms} onChange={e => setFilters(f => ({ ...f, rooms: e.target.value }))}
            className="w-full border rounded-lg px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-blue-500 focus:outline-none">
            <option value="">Любое</option>
            <option value="0">Студия</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4+</option>
          </select>

          <label className="block text-xs text-gray-600 mb-1">Цена (₽)</label>
          <div className="flex gap-2 mb-3">
            <input type="number" placeholder="От" value={filters.price_min}
              onChange={e => setFilters(f => ({ ...f, price_min: e.target.value }))}
              className="w-1/2 border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
            <input type="number" placeholder="До" value={filters.price_max}
              onChange={e => setFilters(f => ({ ...f, price_max: e.target.value }))}
              className="w-1/2 border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
          </div>

          <button onClick={applyFilters}
            className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">
            🔍 Найти
          </button>
        </div>

        <div className="p-3 border-t text-xs text-gray-400 text-center">
          MVP v0.2 • {total} объявлений
        </div>
      </aside>

      {/* ═══ Main ══════════════════════════════════════════ */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <div className="lg:hidden flex items-center gap-3 p-3 border-b bg-white">
          <button onClick={() => setSidebarOpen(true)} className="p-1">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 className="font-bold text-blue-600">🏠 Realty AI</h1>
        </div>

        {view === 'chat' ? (
          <>
            <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-3">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`chat-bubble ${msg.role} max-w-[85%] md:max-w-[70%]`}>
                    {msg.role === 'agent' ? (
                      <ReactMarkdown className="prose prose-sm max-w-none">{msg.text}</ReactMarkdown>
                    ) : msg.text}
                  </div>
                </div>
              ))}

              {coldStart && loading && (
                <div className="flex justify-start">
                  <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-2 rounded-xl text-sm">
                    ⏳ Сервер просыпается (Render Free — cold start до 60 сек)...
                  </div>
                </div>
              )}

              {loading && !coldStart && (
                <div className="flex justify-start">
                  <div className="chat-bubble agent animate-pulse">⏳ Ищу...</div>
                </div>
              )}

              {showSkeleton && <SkeletonGrid />}
              <div ref={chatEnd} />
            </div>

            {/* Suggestions */}
            {messages.length <= 2 && (
              <div className="px-4 pb-2 flex flex-wrap gap-2">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} onClick={() => sendMessage(s)}
                    className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-full transition truncate max-w-xs">
                    {s}
                  </button>
                ))}
              </div>
            )}

            {/* Input */}
            <div className="border-t bg-white p-3 md:p-4">
              <div className="flex gap-2 max-w-3xl mx-auto">
                <input value={input} onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder="Спросите о недвижимости..."
                  className="flex-1 border rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={loading} />
                <button onClick={() => sendMessage()} disabled={loading || !input.trim()}
                  className="bg-blue-600 text-white px-5 py-3 rounded-xl hover:bg-blue-700 disabled:opacity-50 transition text-sm font-medium">
                  →
                </button>
              </div>
            </div>
          </>
        ) : (
          /* ═══ Listings ════════════════════════════════════ */
          <div className="flex-1 overflow-y-auto p-4 md:p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Объявления ({total})</h2>
            </div>

            {listings.length === 0 ? (
              <div className="text-center text-gray-400 mt-20">
                <p className="text-5xl mb-4">🏠</p>
                <p className="text-lg mb-2">Нет объявлений</p>
                <p className="text-sm">Попросите AI-агента что-нибудь найти или используйте фильтры</p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {listings.map(item => (
                    <div key={item.id} onClick={() => openDetail(item.id)}
                      className="listing-card group cursor-pointer">
                      <div className="h-40 bg-gray-100 rounded-lg mb-3 flex items-center justify-center overflow-hidden relative">
                        {item.images?.[0] ? (
                          <img src={item.images[0]} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <span className="text-4xl">🏢</span>
                        )}
                        <span className="absolute top-2 right-2 bg-white/80 text-gray-500 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition">
                          ↗ {item.source}
                        </span>
                      </div>

                      <div className="price">{formatPrice(item.price, item.deal_type)}</div>
                      <div className="meta">
                        {PROPERTY_LABELS[item.property_type]} • {DEAL_LABELS[item.deal_type]}
                      </div>
                      <div className="mt-2 text-sm">
                        {item.rooms !== null && <span className="font-medium">{item.rooms === 0 ? 'Студия' : `${item.rooms}-комн.`}</span>}
                        {item.area_m2 && <span> • {item.area_m2} м²</span>}
                        {item.floor && <span> • этаж {item.floor}/{item.floors_total}</span>}
                      </div>
                      <div className="mt-2 text-sm text-gray-600">📍 {item.city}, {item.address}</div>
                      {item.description && <p className="mt-2 text-xs text-gray-400 line-clamp-2">{item.description}</p>}
                      <div className="mt-3 flex items-center justify-between">
                        <span className="text-xs bg-gray-100 px-2 py-1 rounded">{item.source}</span>
                        <span className="text-xs text-blue-600 opacity-0 group-hover:opacity-100 transition">Подробнее →</span>
                      </div>
                    </div>
                  ))}
                </div>

                {offset < total && (
                  <div className="mt-6 text-center">
                    <button onClick={loadMore} disabled={loadingMore}
                      className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-6 py-3 rounded-xl text-sm font-medium transition disabled:opacity-50">
                      {loadingMore ? '⏳ Загрузка...' : `Показать ещё (${total - offset} осталось)`}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
