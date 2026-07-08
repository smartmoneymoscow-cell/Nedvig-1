import './globals.css';

export const metadata = {
  title: 'Realty AI — Умный поиск недвижимости на карте',
  description: 'Агрегатор недвижимости с AI-агентом и картой. Квартиры, дома, коммерция из 7 источников.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="h-screen overflow-hidden">{children}</body>
    </html>
  );
}
