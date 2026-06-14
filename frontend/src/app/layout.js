import './globals.css'

export const metadata = {
  title: 'Wound-Splat',
  description: '3D Wound Monitoring System',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
