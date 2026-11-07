export function googleDirectionsUrl(lat: number, lon: number, name?: string): string {
  const dest = name ? `${name}@${lat},${lon}` : `${lat},${lon}`;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}`;
}

export function googlePlaceUrl(lat: number, lon: number, name: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name)}&query=${lat},${lon}`;
}
