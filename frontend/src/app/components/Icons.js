export function Icon({ name, size = 18 }) {
  const common = { width:size, height:size, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', strokeWidth:'1.8', strokeLinecap:'round', strokeLinejoin:'round', 'aria-hidden':'true' }
  const paths = {
    upload: <><path d="M12 16V4"/><path d="M7.5 8.5 12 4l4.5 4.5"/><path d="M5 20h14"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    patient: <><circle cx="12" cy="8" r="3.5"/><path d="M5.5 20c.7-4 3-6 6.5-6s5.8 2 6.5 6"/></>,
    activity: <><path d="M3 12h4l2.2-5 4.1 10 2.2-5H21"/></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    search: <><circle cx="11" cy="11" r="6"/><path d="M16 16l4 4"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    file: <><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h5M10 13h5M10 17h5"/></>,
    camera: <><path d="M4 7h4l1.5-2h5L16 7h4v12H4z"/><circle cx="12" cy="13" r="3"/></>,
    eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z"/><circle cx="12" cy="12" r="2.5"/></>,
    download: <><path d="M12 4v12M7.5 11.5 12 16l4.5-4.5"/><path d="M5 20h14"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  }
  return <svg {...common}>{paths[name]}</svg>
}
