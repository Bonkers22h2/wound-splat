import test from 'node:test'
import assert from 'node:assert/strict'
import { drawBox, imageNaturalSize, moveBox, resizeBox } from './selection.mjs'

test('a cached image that already completed exposes its natural dimensions', () => {
  assert.deepEqual(imageNaturalSize({ complete: true, naturalWidth: 1080, naturalHeight: 1920 }),
    { width: 1080, height: 1920 })
  assert.equal(imageNaturalSize({ complete: false, naturalWidth: 1080, naturalHeight: 1920 }), null)
  assert.equal(imageNaturalSize({ complete: true, naturalWidth: 0, naturalHeight: 0 }), null)
})

test('drawing backwards produces the same original-image coordinates', () => {
  assert.deepEqual(drawBox({ x: 800, y: 900 }, { x: 100, y: 200 }),
    { left: 100, top: 200, right: 800, bottom: 900 })
})
test('moving against an image edge preserves the selection size', () => {
  assert.deepEqual(moveBox({ left: 100, top: 200, right: 400, bottom: 600 },
    -200, 900, { width: 1000, height: 1200 }),
  { left: 0, top: 800, right: 300, bottom: 1200 })
})
test('resizing cannot cross the opposite corner or exceed the image', () => {
  const box = { left: 100, top: 200, right: 400, bottom: 600 }
  assert.deepEqual(resizeBox(box, 'nw', { x: 900, y: -20 }, { width: 1000, height: 1200 }),
    { left: 392, top: 0, right: 400, bottom: 600 })
  assert.deepEqual(resizeBox(box, 'se', { x: 2000, y: 2000 }, { width: 1000, height: 1200 }),
    { left: 100, top: 200, right: 1000, bottom: 1200 })
})
