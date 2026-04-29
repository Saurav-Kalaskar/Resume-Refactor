# Design System

**Aesthetic:** Native macOS (MacBook) window UI.
**Style:** Strict, premium design system.
**Core Elements:** 
- Heavy glassmorphism
- Translucent frosted glass panels (e.g. `backdrop-filter: blur(20px) saturate(180%); background: rgba(255, 255, 255, 0.05);` for dark mode).
- Mirror finishes with subtle 1px white/gray borders to simulate glass edges (`border: 1px solid rgba(255, 255, 255, 0.1)`).
- Dynamically changing glowing elements: animated glowing gradients on active borders, inputs, and hover states. Use CSS animations to make gradients slowly rotate or pulse.
**Typography:** High-contrast pairings. Primary font (Headers): 'Satoshi', sans-serif. Secondary/Body/Inputs: 'Space Grotesk', sans-serif (or 'JetBrains Mono' for code/data).
**Colors:** macOS inspired deep grays/blacks for the background (like macOS dark mode wallpaper), vibrant accent colors (like glowing purple/pink or electric blue gradients), and high contrast white text.
