# Cabeceras de seguridad. Los estilos inline (style="...") que genera
# app.js obligan a 'unsafe-inline' en style-src; los scripts no tienen
# nada inline (los onerror se gestionan desde app.js), así que script-src
# queda en 'self'. Las fotos de jugadores vienen del CDN de Mister.
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://cdn-mister.mundodeportivo.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
