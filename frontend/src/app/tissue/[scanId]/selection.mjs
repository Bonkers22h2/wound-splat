const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
export function imageNaturalSize(image) {
  if (!image?.complete || !image.naturalWidth || !image.naturalHeight) return null
  return { width: image.naturalWidth, height: image.naturalHeight }
}
export function drawBox(a, b) {
  return { left: Math.min(a.x, b.x), top: Math.min(a.y, b.y), right: Math.max(a.x, b.x), bottom: Math.max(a.y, b.y) }
}
export function moveBox(box, dx, dy, size) {
  dx = clamp(dx, -box.left, size.width - box.right)
  dy = clamp(dy, -box.top, size.height - box.bottom)
  return { left: box.left + dx, top: box.top + dy, right: box.right + dx, bottom: box.bottom + dy }
}
export function resizeBox(box, corner, point, size) {
  const next = { ...box }
  if (corner.includes('w')) next.left = clamp(point.x, 0, box.right - 8)
  if (corner.includes('e')) next.right = clamp(point.x, box.left + 8, size.width)
  if (corner.includes('n')) next.top = clamp(point.y, 0, box.bottom - 8)
  if (corner.includes('s')) next.bottom = clamp(point.y, box.top + 8, size.height)
  return next
}
