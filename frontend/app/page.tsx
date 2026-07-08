'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import dynamic from 'next/dynamic';

const MapView = dynamic(() => import('../components/MapView'), { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/* ═══ Types ═══════════════════════════════════════════════════ */

interface Listing {
  id: string; source: string; source_url: string; property_type: string;
  deal_type: string; price: number; currency: string; area_m2: number | null;
  rooms: number | null; floor: number | null; floors_total: number | null;
  address: string; city: string; district: string | null;
  description: string | null; images: string[]; lat: number | null; lon: number | null;
}

interface Message { role: 'user' | 'agent'; text: string; filters?: Record<string, any>; }

/* ═══ Constants ═══════════════════════════════════════════════ */

const CITIES: { name: string; lat: number; lon: number; zoom: number }[] = [
  { name: 'Москва', lat: 55.75, lon: 37.62, zoom: 10 },
  { name: 'Санкт-Петербург', lat: 59.93, lon: 30.32, zoom: 10 },
  { name: 'Новосибирск', lat: 55.03, lon: 82.92, zoom: 11 },
  { name: 'Екатеринбург', lat: 56.84, lon: 60.60, zoom: 11 },
  { name: 'Казань', lat: 55.79, lon: 49.12, zoom: 11 },
  { name: 'Краснодар', lat: 45.04, lon: 38.98, zoom: 11 },
  { name: 'Сочи', lat: 43.60, lon: 39.73, zoom: 12 },
  { name: 'Самара', lat: 53.20, lon: 50.15, zoom: 11 },
  { name: 'Уфа', lat: 54.74, lon: 55.97, zoom: 11 },
  { name: 'Владивосток', lat: 43.12, lon: 131.89, zoom: 11 },
];

const PROPERTY_LABELS: Record<string, string> = {
  apartment: 'Квартира', house: 'Дом', commercial: 'Коммерция',
  land: 'Участок', room: 'Комната', studio: 'Студия',
};
const DEAL_LABELS: Record<string, string> = { sale: 'Продажа', rent: 'Аренда' };

const SOURCE_COLORS: Record<string, string> = {
  cian: '#00a0e1', domclick: '#ff6a00', avito: '#ff4f00',
  n1: '#6e2fee', yandex: '#fc3f1d', irr: '#4caf50', bn: '#2196f3',
  seed: '#9e9e9e',
};

const AI_STEPS = [
  { key: 'city', question: '🏙️ В каком городе ищете недвижимость?', options: ['Москва', 'Санкт-Петербург', 'Краснодар', 'Сочи', 'Другой'] },
  { key: 'deal', question: '💰 Покупка или аренда?', options: ['Покупка', 'Аренда'] },
  { key: 'type', question: '🏢 Какой тип недвижимости?', options: ['Квартира', 'Студия', 'Дом', 'Коммерция', 'Любой'] },
  { key: 'rooms', question: '🚪 Сколько комнат?', options: ['1', '2', '3', '4+', 'Любое'] },
  { key: 'budget', question: '💳 Какой бюджет?', options: ['До 5 млн', '5-10 млн', '10-20 млн', '20+ млн', 'Не важно'] },
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
  return new Intl.NumberFormat('ru-RU').format(price) + ' ₽';
}

function formatPriceShort(price: number): string {
  if (price >= 1_000_000) return (price / 1_000_000).toFixed(1) + 'М';
  if (price >= 1_000) return (price / 1_000).toFixed(0) + 'К';
  return String(price);
}

/* ═══ City Popup ══════════════════════════════════════════════ */

function CityPopup({ onSelect }: { onSelect: (city: string) => void }) {
  return (
    <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
        <h2 className="text-2xl font-bold text-center mb-2">🏠 Realty AI</h2>
        <p className="text-gray-500 text-center mb-6">Выберите город для начала работы</p>

        <div className="space-y-2">
          {CITIES.map(c => (
            <button key={c.name} onClick={() => onSelect(c.name)}
              className="w-full text-left px-4 py-3 rounded-xl border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition flex items-center justify-between group">
              <span className="font-medium">{c.name}</span>
              <span className="text-gray-400 group-hover:text-blue-600 transition">→</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══ Marker Hover Card ═══════════════════════════════════════ */

function HoverCard({ listing, onClose }: { listing: Listing; onClose: () => void }) {
  return (
    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50" onClick={e => e.stopPropagation()}>
      <div className="bg-white rounded-xl shadow-xl border w-72 overflow-hidden">
        <div className="h-32 bg-gray-100 relative">
          {listing.images?.[0] ? (
            <img src={listing.images[0]} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-3xl">🏢</div>
          )}
          <span className="absolute top-2 left-2 text-white text-xs font-bold px-2 py-1 rounded"
            style={{ background: SOURCE_COLORS[listing.source] || '#666' }}>
            {listing.source}
          </span>
          <button onClick={onClose} className="absolute top-2 right-2 bg-white/80 w-6 h-6 rounded-full flex items-center justify-center text-xs hover:bg-white">✕</button>
        </div>
        <div className="p-3">
          <div className="text-lg font-bold text-blue-600">{formatPrice(listing.price, listing.deal_type)}</div>
          <div className="text-sm text-gray-500 mt-0.5">
            {listing.rooms !== null ? (listing.rooms === 0 ? 'Студия' : `${listing.rooms}-комн.`) : PROPERTY_LABELS[listing.property_type]}
            {listing.area_m2 && ` • ${listing.area_m2} м²`}
            {listing.floor && ` • ${listing.floor}/${listing.floors_total} этаж`}
          </div>
          <div className="text-xs text-gray-400 mt-1">📍 {listing.city}, {listing.address}</div>
          {listing.description && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{listing.description}</p>}
          <a href={listing.source_url} target="_blank" rel="noopener noreferrer"
            className="block mt-2 text-center bg-blue-600 text-white text-xs py-2 rounded-lg hover:bg-blue-700 transition">
            Открыть на {listing.source} ↗
          </a>
        </div>
      </div>
    </div>
  );
}

/* ═══ Main Component ═════════════════════════════════════════ */

export default function Home() {
  /* ── State ─────────────────────────────────────────────── */
  const [showCityPopup, setShowCityPopup] = useState(() => {
    if (typeof window !== 'undefined') return !localStorage.getItem('nedvig_city');
    return true;
  });
  const [selectedCity, setSelectedCity] = useState(() => {
    if (typeof window !== 'undefined') return localStorage.getItem('nedvig_city') || '';
    return '';
  });
  const [mapCenter, setMapCenter] = useState<[number, number]>(() => {
    const city = CITIES.find(c => c.name === selectedCity);
    return city ? [city.lat, city.lon] : [55.75, 37.62];
  });
  const [mapZoom, setMapZoom] = useState(() => {
    const city = CITIES.find(c => c.name === selectedCity);
    return city ? city.zoom : 10;
  });

  const [listings, setListings] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarTab, setSidebarTab] = useState<'chat' | 'filters'>('filters');
  const [hoveredListing, setHoveredListing] = useState<Listing | null>(null);

  /* AI chat state */
  const [messages, setMessages] = useState<Message[]>([
    { role: 'agent', text: '👋 Привет! Я помогу подобрать недвижимость. Давайте пошагово определим ваши параметры.' },
  ]);
  const [aiStep, setAiStep] = useState(0);
  const [aiAnswers, setAiAnswers] = useState<Record<string, string>>({});
  const [aiInput, setAiInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);

  /* Manual filter state */
  const [fDeal, setFDeal] = useState('');
  const [fType, setFType] = useState('');
  const [fRooms, setFRooms] = useState('');
  const [fPriceMin, setFPriceMin] = useState('');
  const [fPriceMax, setFPriceMax] = useState('');

  /* ── Effects ───────────────────────────────────────────── */
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load ALL listings on mount
  useEffect(() => {
    loadListings();
  }, []);

  // When city changes, reload listings for that city
  useEffect(() => {
    if (selectedCity) {
      const city = CITIES.find(c => c.name === selectedCity);
      if (city) {
        setMapCenter([city.lat, city.lon]);
        setMapZoom(city.zoom);
        loadListings({ city: selectedCity });
      }
    }
  }, [selectedCity]);

  /* ── City select ───────────────────────────────────────── */
  const selectCity = (city: string) => {
    setSelectedCity(city);
    localStorage.setItem('nedvig_city', city);
    setShowCityPopup(false);
  };

  /* ── Load listings ─────────────────────────────────────── */
  const loadListings = async (filters: Record<string, any> = {}) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.city) params.set('city', filters.city);
      if (filters.deal_type) params.set('deal_type', filters.deal_type);
      if (filters.property_type) params.set('property_type', filters.property_type);
      if (filters.rooms) params.set('rooms', String(filters.rooms));
      if (filters.price_min) params.set('price_min', String(filters.price_min));
      if (filters.price_max) params.set('price_max', String(filters.price_max));

      const res = await fetch(`${API}/api/listings?${params}`);
      const data = await res.json();
      setListings(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error('Load error:', e);
    }
    setLoading(false);
  };

  /* ── Manual search ─────────────────────────────────────── */
  const manualSearch = () => {
    const filters: Record<string, any> = { city: selectedCity };
    if (fDeal) filters.deal_type = fDeal;
    if (fType) filters.property_type = fType;
    if (fRooms) filters.rooms = fRooms;
    if (fPriceMin) filters.price_min = Number(fPriceMin);
    if (fPriceMax) filters.price_max = Number(fPriceMax);
    loadListings(filters);
  };

  /* ── AI chat flow ──────────────────────────────────────── */
  const handleAiOption = async (option: string) => {
    const step = AI_STEPS[aiStep];
    const newAnswers = { ...aiAnswers, [step.key]: option };
    setAiAnswers(newAnswers);

    setMessages(prev => [...prev, { role: 'user', text: option }]);

    if (aiStep < AI_STEPS.length - 1) {
      const nextStep = AI_STEPS[aiStep + 1];
      setMessages(prev => [...prev, { role: 'agent', text: nextStep.question }]);
      setAiStep(aiStep + 1);
    } else {
      // All steps done — build query and search
      setMessages(prev => [...prev, { role: 'agent', text: '🔍 Ищу по вашим параметрам...' }]);
      setAiLoading(true);

      const query = buildAiQuery(newAnswers);
      try {
        const res = await fetch(`${API}/api/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query }),
        });
        const data = await res.json();
        setMessages(prev => [...prev, { role: 'agent', text: data.response || 'Ничего не найдено' }]);

        if (data.total > 0) {
          const params = new URLSearchParams();
          if (data.filters?.city) params.set('city', data.filters.city);
          if (data.filters?.deal_type) params.set('deal_type', data.filters.deal_type);
          if (data.filters?.property_type) params.set('property_type', data.filters.property_type);
          if (data.filters?.rooms) params.set('rooms', String(data.filters.rooms));
          if (data.filters?.price_max) params.set('price_max', String(data.filters.price_max));

          const listRes = await fetch(`${API}/api/listings?${params}`);
          const listData = await listRes.json();
          setListings(listData.items || []);
          setTotal(listData.total || 0);

          // Zoom to city
          const city = CITIES.find(c => c.name === (newAnswers.city || selectedCity));
          if (city) {
            setMapCenter([city.lat, city.lon]);
            setMapZoom(city.zoom);
          }
        }
      } catch {
        setMessages(prev => [...prev, { role: 'agent', text: '❌ Ошибка соединения с сервером' }]);
      }
      setAiLoading(false);
    }
  };

  const handleAiInput = async () => {
    if (!aiInput.trim()) return;
    const text = aiInput.trim();
    setAiInput('');
    setMessages(prev => [...prev, { role: 'user', text }]);
    setAiLoading(true);

    try {
      const res = await fetch(`${API}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      });
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'agent', text: data.response || 'Не удалось обработать' }]);
      if (data.total > 0) {
        const params = new URLSearchParams();
        if (data.filters?.city) params.set('city', data.filters.city);
        if (data.filters?.deal_type) params.set('deal_type', data.filters.deal_type);
        if (data.filters?.property_type) params.set('property_type', data.filters.property_type);
        if (data.filters?.rooms) params.set('rooms', String(data.filters.rooms));
        const listRes = await fetch(`${API}/api/listings?${params}`);
        const listData = await listRes.json();
        setListings(listData.items || []);
        setTotal(listData.total || 0);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'agent', text: '❌ Ошибка соединения' }]);
    }
    setAiLoading(false);
  };

  const resetAi = () => {
    setAiStep(0);
    setAiAnswers({});
    setMessages([{ role: 'agent', text: AI_STEPS[0].question }]);
  };

  function buildAiQuery(answers: Record<string, string>): string {
    const parts: string[] = [];
    if (answers.city && answers.city !== 'Другой') parts.push(answers.city);
    if (answers.deal === 'Аренду' || answers.deal === 'Аренда') parts.push('в аренду');
    else if (answers.deal) parts.push('купить');
    if (answers.type && answers.type !== 'Любой') parts.push(answers.type.toLowerCase());
    if (answers.rooms && answers.rooms !== 'Любое') parts.push(`${answers.rooms}-комнатная`);
    if (answers.budget && answers.budget !== 'Не важно') {
      const budgetMap: Record<string, string> = {
        'До 5 млн': 'до 5 млн', '5-10 млн': 'от 5 до 10 млн',
        '10-20 млн': 'от 10 до 20 млн', '20+ млн': 'от 20 млн',
      };
      if (budgetMap[answers.budget]) parts.push(budgetMap[answers.budget]);
    }
    return parts.join(' ') || 'квартира';
  }

  /* ── Map marker click ──────────────────────────────────── */
  const onMarkerClick = (listing: Listing) => {
    setHoveredListing(prev => prev?.id === listing.id ? null : listing);
  };

  /* ═══ RENDER ════════════════════════════════════════════ */

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-gray-50">
      {/* City popup */}
      {showCityPopup && <CityPopup onSelect={selectCity} />}

      {/* ═══ Top Bar ═══════════════════════════════════════ */}
      <header className="h-14 bg-white border-b flex items-center px-4 gap-4 z-20 flex-shrink-0">
        <button className="lg:hidden p-1" onClick={() => setSidebarOpen(!sidebarOpen)}>
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <h1 className="text-lg font-bold text-blue-600 flex-shrink-0">🏠 Realty AI</h1>

        {/* City selector */}
        <button onClick={() => setShowCityPopup(true)}
          className="flex items-center gap-1 text-sm text-gray-600 hover:text-blue-600 transition">
          📍 {selectedCity || 'Выберите город'}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <div className="flex-1" />

        {/* Stats */}
        <div className="hidden md:flex items-center gap-4 text-sm text-gray-500">
          <span>🏢 {total} объявлений</span>
          <span className="text-xs bg-gray-100 px-2 py-1 rounded">7 источников</span>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        {/* ═══ Sidebar ═════════════════════════════════════ */}
        <aside className={`
          fixed lg:static inset-y-14 left-0 z-30 w-80 bg-white border-r
          flex flex-col transform transition-transform duration-200
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0 lg:w-0 lg:border-0'}
          ${!sidebarOpen ? 'lg:overflow-hidden' : ''}
        `}>
          {/* Tabs */}
          <div className="flex border-b">
            <button onClick={() => setSidebarTab('filters')}
              className={`flex-1 py-3 text-sm font-medium ${sidebarTab === 'filters' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'}`}>
              🔍 Поиск
            </button>
            <button onClick={() => setSidebarTab('chat')}
              className={`flex-1 py-3 text-sm font-medium ${sidebarTab === 'chat' ? 'text-white bg-gradient-to-r from-blue-600 to-cyan-500 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700 hover:bg-blue-50'}`}>
              🤖 AI-Чат
            </button>
          </div>

          {/* Filters tab */}
          {sidebarTab === 'filters' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Город</label>
                <select value={selectedCity} onChange={e => selectCity(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none bg-white">
                  <option value="">Выберите город</option>
                  {CITIES.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Тип сделки</label>
                <div className="flex gap-2">
                  <button onClick={() => setFDeal(fDeal === 'sale' ? '' : 'sale')}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium border transition ${fDeal === 'sale' ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 hover:border-blue-300'}`}>
                    Покупка
                  </button>
                  <button onClick={() => setFDeal(fDeal === 'rent' ? '' : 'rent')}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium border transition ${fDeal === 'rent' ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 hover:border-blue-300'}`}>
                    Аренда
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Тип недвижимости</label>
                <select value={fType} onChange={e => setFType(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
                  <option value="">Любой</option>
                  {Object.entries(PROPERTY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Комнаты</label>
                <div className="flex gap-1.5">
                  {['', '0', '1', '2', '3', '4'].map(r => (
                    <button key={r} onClick={() => setFRooms(r === fRooms ? '' : r)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border transition ${r === fRooms ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 hover:border-blue-300'}`}>
                      {r === '' ? 'Любое' : r === '0' ? 'Студ' : r === '4' ? '4+' : r}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Цена (₽)</label>
                <div className="flex gap-2">
                  <input type="number" placeholder="От" value={fPriceMin} onChange={e => setFPriceMin(e.target.value)}
                    className="w-1/2 border rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                  <input type="number" placeholder="До" value={fPriceMax} onChange={e => setFPriceMax(e.target.value)}
                    className="w-1/2 border rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
              </div>

              <button onClick={manualSearch} disabled={loading || !selectedCity}
                className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition disabled:opacity-50 text-sm">
                {loading ? '⏳ Поиск...' : '🔍 Найти'}
              </button>

              {/* Results summary */}
              {total > 0 && (
                <div className="text-xs text-gray-500 text-center pt-2 border-t">
                  Найдено {total} объявлений • Показаны на карте
                </div>
              )}
            </div>
          )}

          {/* AI Chat tab */}
          {sidebarTab === 'chat' && (
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[90%] px-4 py-2.5 rounded-2xl text-sm ${msg.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-md'
                        : 'bg-gray-100 text-gray-800 rounded-bl-md'
                      }`}>
                      {msg.role === 'agent' ? (
                        <ReactMarkdown className="prose prose-sm max-w-none">{msg.text}</ReactMarkdown>
                      ) : msg.text}
                    </div>
                  </div>
                ))}

                {/* AI options */}
                {!aiLoading && aiStep < AI_STEPS.length && (
                  <div className="flex flex-wrap gap-2">
                    {AI_STEPS[aiStep].options.map(opt => (
                      <button key={opt} onClick={() => handleAiOption(opt)}
                        className="text-xs bg-white border border-blue-200 text-blue-600 px-3 py-1.5 rounded-full hover:bg-blue-50 transition">
                        {opt}
                      </button>
                    ))}
                  </div>
                )}

                {aiLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-md text-sm animate-pulse">⏳ Ищу...</div>
                  </div>
                )}

                <div ref={chatEnd} />
              </div>

              {/* Free text input */}
              <div className="border-t p-3 flex gap-2">
                <input value={aiInput} onChange={e => setAiInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAiInput()}
                  placeholder="Или напишите запрос..."
                  className="flex-1 border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                <button onClick={handleAiInput}
                  className="bg-blue-600 text-white px-4 rounded-xl hover:bg-blue-700 transition text-sm">→</button>
              </div>

              {/* Reset */}
              <div className="px-4 pb-3">
                <button onClick={resetAi} className="text-xs text-gray-400 hover:text-gray-600 transition">
                  🔄 Начать заново
                </button>
              </div>
            </div>
          )}
        </aside>

        {/* Mobile sidebar overlay */}
        {sidebarOpen && (
          <div className="fixed inset-0 bg-black/20 z-20 lg:hidden" onClick={() => setSidebarOpen(false)} />
        )}

        {/* ═══ Map ═════════════════════════════════════════ */}
        <div className="flex-1 relative">
          <MapView
            center={mapCenter}
            zoom={mapZoom}
            listings={listings}
            hoveredId={hoveredListing?.id || null}
            onMarkerClick={onMarkerClick}
            sourceColors={SOURCE_COLORS}
          />

          {/* Hover card */}
          {hoveredListing && (
            <div className="absolute top-4 right-4 z-50">
              <HoverCard listing={hoveredListing} onClose={() => setHoveredListing(null)} />
            </div>
          )}

          {/* Loading overlay */}
          {loading && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-40 bg-white shadow-lg rounded-full px-4 py-2 text-sm text-gray-600 flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              Загрузка...
            </div>
          )}

          {/* Toggle sidebar button */}
          {!sidebarOpen && (
            <button onClick={() => setSidebarOpen(true)}
              className="absolute top-4 left-4 z-30 bg-white shadow-lg rounded-xl p-3 hover:bg-gray-50 transition">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
