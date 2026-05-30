import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon   from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl:       markerIcon,
  shadowUrl:     markerShadow,
});

export const greenIcon = L.icon({
  iconUrl:    'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl:  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize:   [25, 41],
  iconAnchor: [12, 41],
  popupAnchor:[1, -34],
  shadowSize: [41, 41],
});

export function makeNumberIcon(num) {
  return L.divIcon({
    className: '',
    html: `<div style="
      background:#2563eb;
      width:26px;height:26px;
      border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      color:white;font-size:11px;font-weight:bold;
      border:2px solid white;
      box-shadow:0 2px 4px rgba(0,0,0,0.35);
    ">${num}</div>`,
    iconSize:    [26, 26],
    iconAnchor:  [13, 13],
    popupAnchor: [0, -16],
  });
}

function ChangeView({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.setView(center, zoom);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center?.[0], center?.[1], zoom]);
  return null;
}

function LeafletMap({
  center,
  zoom          = 12,
  height        = '400px',
  polyline      = [],
  polylineColor = '#4285F4',
  markers       = [],
  mapKey,
  children,
}) {
  if (!center) return null;

  return (
    <MapContainer
      key={mapKey}
      center={center}
      zoom={zoom}
      style={{ height, width: '100%', borderRadius: '4px', zIndex: 0 }}
      scrollWheelZoom
    >
      <ChangeView center={center} zoom={zoom} />

      {/* Tile layer OpenStreetMap */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Polyline rute */}
      {polyline.length > 0 && (
        <Polyline
          positions={polyline}
          color={polylineColor}
          weight={4}
          opacity={0.9}
        />
      )}

      {/* Markers */}
      {markers.map((marker, idx) => {
        let icon = new L.Icon.Default();
        if (marker.color === 'green') {
          icon = greenIcon;
        } else if (marker.label != null) {
          icon = makeNumberIcon(marker.label);
        }

        return (
          <Marker
            key={idx}
            position={[marker.lat, marker.lng]}
            icon={icon}
          >
            {marker.popup && <Popup>{marker.popup}</Popup>}
          </Marker>
        );
      })}

      {/* Slot untuk elemen react-leaflet tambahan dari parent */}
      {children}
    </MapContainer>
  );
}

export default LeafletMap;
