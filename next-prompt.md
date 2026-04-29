---
page: App
---
Generate the main application dashboard for the ATS Resume Refactoring Engine.

**DESIGN SYSTEM (REQUIRED):**
Aesthetic: Native macOS (MacBook) window UI.
Style: Strict, premium design system.
Core Elements: 
- Heavy glassmorphism
- Translucent frosted glass panels (e.g. `backdrop-filter: blur(20px) saturate(180%); background: rgba(255, 255, 255, 0.05);`).
- Mirror finishes with subtle 1px translucent borders to simulate glass edges (`border: 1px solid rgba(255, 255, 255, 0.1)`).
- Dynamically changing glowing elements: animated glowing gradients on active borders, inputs, and hover states. Use CSS animations.
- Dark mode primary theme with a beautiful dark abstract background, and vibrant, glowing accent colors.
Typography: High-contrast pairings. Headers: 'Satoshi'. Body/Inputs: 'Space Grotesk' or 'JetBrains Mono'. Use elegant letter-spacing.

**Page Structure:**
A single-page dashboard containing:
1. A container that looks like a floating macOS window, complete with the 3 traffic light dots (close, minimize, maximize) in the top-left corner.
2. The window is divided into a layout suitable for a dashboard.
3. 'Company Name' input field (sleek, glowing on focus).
4. Job Description text area.
5. Drag-and-drop file upload zone (frosted glass, animated border).
6. A 'Refactor Resume' action button (vibrant gradient, glowing).
7. A responsive PDF preview container (shows a skeleton loader or a mock PDF view, with a mobile fallback).

Ensure you include all necessary HTML and CSS (Vanilla CSS in a `<style>` block is preferred for complex glassmorphism, or Tailwind if you can achieve the heavy glass look). Make it look extremely premium, visually stunning, and responsive.
