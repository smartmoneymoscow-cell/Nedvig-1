import './globals.css';

export const metadata = {
  title: 'Realty AI — Умный поиск недвижимости',
  description: 'Агрегатор недвижимости с AI-агентом. Поиск квартир, домов, коммерческой недвижимости.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-screen bg-gray-50" style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>{children}</body>
    </html>
  );
}
