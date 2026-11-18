import React from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import ItemSearchIsland from './islands/ItemSearchIsland';
import PricePreviewIsland from './islands/PricePreviewIsland';

function mountIslands() {
  // 1. Mount Item Search Island
  const searchEl = document.getElementById('item-search-island');
  if (searchEl) {
    try {
      const searchUrl = searchEl.dataset.searchUrl || '/catalog/search-json/';
      const initialQ = searchEl.dataset.initialQ || '';
      const initialCategory = searchEl.dataset.initialCategory || '';
      const initialCity = searchEl.dataset.initialCity || '';
      const initialMaxPrice = searchEl.dataset.initialMaxPrice || '';
      const categories = searchEl.dataset.categories ? JSON.parse(searchEl.dataset.categories) : [];
      const cities = searchEl.dataset.cities ? JSON.parse(searchEl.dataset.cities) : [];

      const root = createRoot(searchEl);
      root.render(
        <React.StrictMode>
          <ItemSearchIsland
            searchUrl={searchUrl}
            initialQ={initialQ}
            initialCategory={initialCategory}
            initialCity={initialCity}
            initialMaxPrice={initialMaxPrice}
            categories={categories}
            cities={cities}
          />
        </React.StrictMode>
      );
    } catch (err) {
      console.error('Failed to mount ItemSearchIsland:', err);
    }
  }

  // 2. Mount Price Preview Island
  const previewEl = document.getElementById('price-preview-island');
  if (previewEl) {
    try {
      const itemId = Number(previewEl.dataset.itemId);
      const previewUrl = previewEl.dataset.previewUrl || '/rentals/price-preview-json/';
      const dailyPrice = Number(previewEl.dataset.dailyPrice || 0);
      const hourlyPrice = previewEl.dataset.hourlyPrice ? Number(previewEl.dataset.hourlyPrice) : null;
      const depositAmount = Number(previewEl.dataset.depositAmount || 0);

      const root = createRoot(previewEl);
      root.render(
        <React.StrictMode>
          <PricePreviewIsland
            itemId={itemId}
            previewUrl={previewUrl}
            dailyPrice={dailyPrice}
            hourlyPrice={hourlyPrice}
            depositAmount={depositAmount}
          />
        </React.StrictMode>
      );
    } catch (err) {
      console.error('Failed to mount PricePreviewIsland:', err);
    }
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountIslands);
} else {
  mountIslands();
}
