'use client';

import { useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface Listing {
  id: string; source: string; source_url: string; property_type: string;
  deal_type: string; price: number; area_m2: number | null;
  rooms: number | null; floor: number | null; floors_total: number | null;
  address: string; city: string; description: string | null;
  images: string[]; lat: number | null; lon: number | null;
}

interface MapViewProps {
  center: [number, number];
  zoom: number;
  listings: Listing[];
  hoveredId: string | null;
  onMarkerClick: (listing: Listing) => void;
  sourceColors: Record<string, string>;
}

function formatPriceShort(price: number): string {
  if (price >= 1_000_000) return (price / 1_000_000).toFixed(1) + 'М';
  if (price >= 1_000) return (price / 1_000).toFixed(0) + 'К';
  return String(price);
}

export default function MapView({ center, zoom, listings, hoveredId, onMarkerClick, sourceColors }: MapViewProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const markersLayer = useRef<L.LayerGroup | null>(null);
  const clickRef = useRef(onMarkerClick);

  clickRef.current = onMarkerClick;

  // Init map
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    const map = L.map(mapRef.current, {
      zoomControl: false,
      attributionControl: false,
    }).setView(center, zoom);

    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.control.attribution({ position: 'bottomleft', prefix: false }).addTo(map);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OSM',
      maxZoom: 19,
    }).addTo(map);

    markersLayer.current = L.layerGroup().addTo(map);
    mapInstance.current = map;

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  // Update view
  useEffect(() => {
    if (mapInstance.current) {
      mapInstance.current.flyTo(center, zoom, { duration: 1 });
    }
  }, [center, zoom]);

  // Update markers
  useEffect(() => {
    if (!markersLayer.current) return;
    markersLayer.current.clearLayers();

    const validListings = listings.filter(l => l.lat && l.lon);

    validListings.forEach(listing => {
      const color = sourceColors[listing.source] || '#666';
      const priceLabel = formatPriceShort(listing.price);
      const isHovered = hoveredId === listing.id;

      const icon = L.divIcon({
        className: 'custom-marker',
        html: `
          <div style="
            position: relative;
            background: ${color};
            color: white;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 8px;
            white-space: nowrap;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            transform: ${isHovered ? 'scale(1.2)' : 'scale(1)'};
            transition: transform 0.15s;
            cursor: pointer;
            font-family: Inter, system-ui, sans-serif;
          ">
            ${priceLabel} ₽
            <div style="
              position: absolute;
              bottom: -5px;
              left: 50%;
              transform: translateX(-50%);
              width: 0; height: 0;
              border-left: 5px solid transparent;
              border-right: 5px solid transparent;
              border-top: 5px solid ${color};
            "></div>
          </div>
        `,
        iconSize: [0, 0],
        iconAnchor: [30, 35],
      });

      const marker = L.marker([listing.lat!, listing.lon!], { icon });

      marker.on('click', () => clickRef.current(listing));

      marker.bindTooltip(
        `<div style="font-family:Inter,system-ui,sans-serif;max-width:200px">
          <div style="font-weight:700;color:#2563eb;margin-bottom:2px">${formatPrice(listing.price, listing.deal_type)}</div>
          <div style="font-size:11px;color:#666">
            ${listing.rooms !== null ? (listing.rooms === 0 ? 'Студия' : listing.rooms + '-комн.') : ''}
            ${listing.area_m2 ? ' • ' + listing.area_m2 + ' м²' : ''}
          </div>
          <div style="font-size:10px;color:#999;margin-top:2px">📍 ${listing.city}, ${listing.address}</div>
          <div style="font-size:9px;color:${color};margin-top:2px;font-weight:600">${listing.source}</div>
        </div>`,
        {
          direction: 'top',
          offset: [0, -35],
          className: 'custom-tooltip',
        }
      );

      markersLayer.current!.addLayer(marker);
    });
  }, [listings, hoveredId, sourceColors]);

  return <div ref={mapRef} className="w-full h-full" />;
}

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
