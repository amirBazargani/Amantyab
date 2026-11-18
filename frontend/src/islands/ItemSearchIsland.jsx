import React, { useState, useEffect, useRef } from 'react';

export default function ItemSearchIsland({
  searchUrl = '/catalog/search-json/',
  initialQ = '',
  initialCategory = '',
  initialCity = '',
  initialMaxPrice = '',
  categories = [],
  cities = [],
}) {
  const [q, setQ] = useState(initialQ);
  const [category, setCategory] = useState(initialCategory);
  const [city, setCity] = useState(initialCity);
  const [maxPrice, setMaxPrice] = useState(initialMaxPrice);
  const [items, setItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const isFirstRun = useRef(true);

  const fetchItems = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.append('q', q.trim());
      if (category.trim()) params.append('category', category.trim());
      if (city.trim()) params.append('city', city.trim());
      if (maxPrice.trim()) params.append('max_price', maxPrice.trim());

      const url = `${searchUrl}?${params.toString()}`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error('خطا در بارگذاری اطلاعات کالاها');
      }
      const data = await res.json();
      setItems(data.items || []);
      setTotalCount(data.total_count || 0);
    } catch (err) {
      console.error('Item search fetch error:', err);
      setError('خطا در برقراری ارتباط با سرور.');
    } finally {
      setLoading(false);
    }
  };

  // Debounced search on filter change
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchItems();
    }, isFirstRun.current ? 0 : 250);

    isFirstRun.current = false;
    return () => clearTimeout(timer);
  }, [q, category, city, maxPrice]);

  const handleClear = () => {
    setQ('');
    setCategory('');
    setCity('');
    setMaxPrice('');
  };

  const hasActiveFilters = q || category || city || maxPrice;

  return (
    <div className="space-y-6">
      {/* Header with live badge */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 space-x-reverse">
            <h1 className="text-2xl md:text-3xl font-black text-gray-900">کاتالوگ امانت کالا</h1>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">
              ⚡ جستجوی زنده (React Island)
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">ابزار و وسایل مورد نیازتان را از همسایگان خود امانت بگیرید</p>
        </div>
        <div className="text-sm text-gray-600 bg-white px-4 py-2 rounded-xl border border-gray-200 shadow-sm self-start md:self-auto flex items-center space-x-2 space-x-reverse">
          <span>تعداد کالاها:</span>
          <span className="font-bold text-blue-600">
            {loading ? 'در حال جستجو...' : `${totalCount} مورد`}
          </span>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-5 md:p-6">
        <div className="space-y-4">
          {/* Search Input */}
          <div className="relative">
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جستجوی نام کالا، برند یا مشخصات (مثلاً: دریل رونیکس، نردبان، چادر کمپینگ...)"
              className="w-full pl-4 pr-11 py-3 bg-gray-50 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white focus:border-transparent transition"
            />
            <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-gray-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
              </svg>
            </div>
            {loading && (
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <svg className="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
              </div>
            )}
          </div>

          {/* Filters Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Category Filter */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">دسته‌بندی</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full py-2.5 px-3 bg-gray-50 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
              >
                <option value="">همه دسته‌ها</option>
                {categories.map((cat) => (
                  <option key={cat.id || cat.slug} value={cat.slug || cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>

            {/* City Filter */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">شهر</label>
              <input
                type="text"
                list="island-cities-list"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="مثلاً: تهران، اصفهان..."
                className="w-full py-2.5 px-3 bg-gray-50 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
              />
              <datalist id="island-cities-list">
                {cities.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </div>

            {/* Max Price Filter */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">حداکثر قیمت روزانه (تومان)</label>
              <input
                type="number"
                min="0"
                step="1000"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                placeholder="مثلاً: 100000"
                className="w-full py-2.5 px-3 bg-gray-50 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
              />
            </div>

            {/* Action buttons */}
            <div className="flex items-end gap-2">
              <button
                type="button"
                onClick={fetchItems}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 px-4 rounded-xl shadow-sm transition text-sm flex items-center justify-center space-x-1 space-x-reverse"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                </svg>
                <span>بروزرسانی</span>
              </button>
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2.5 px-3 rounded-xl transition text-sm flex items-center justify-center"
                  title="پاک‌سازی فیلترها"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Active filter badges */}
          {hasActiveFilters && (
            <div className="flex flex-wrap items-center gap-2 pt-4 mt-4 border-t border-gray-100 text-xs">
              <span className="text-gray-500 font-medium">فیلترهای فعال:</span>
              {q && (
                <span className="inline-flex items-center bg-blue-50 text-blue-700 px-2.5 py-1 rounded-lg border border-blue-100">
                  عبارت: {q}
                </span>
              )}
              {category && (
                <span className="inline-flex items-center bg-blue-50 text-blue-700 px-2.5 py-1 rounded-lg border border-blue-100">
                  دسته: {category}
                </span>
              )}
              {city && (
                <span className="inline-flex items-center bg-blue-50 text-blue-700 px-2.5 py-1 rounded-lg border border-blue-100">
                  شهر: {city}
                </span>
              )}
              {maxPrice && (
                <span className="inline-flex items-center bg-blue-50 text-blue-700 px-2.5 py-1 rounded-lg border border-blue-100">
                  حداکثر قیمت: {Number(maxPrice).toLocaleString('fa-IR')} تومان
                </span>
              )}
              <button
                type="button"
                onClick={handleClear}
                className="text-red-600 hover:text-red-700 font-medium mr-2"
              >
                حذف همه
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Error notification */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Items Grid */}
      {items.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition flex flex-col group"
            >
              {/* Image */}
              <div className="relative aspect-video w-full bg-gray-100 overflow-hidden">
                {item.image_url ? (
                  <img
                    src={item.image_url}
                    alt={item.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 p-4">
                    <svg className="w-10 h-10 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                    <span className="text-xs">بدون تصویر</span>
                  </div>
                )}
                {/* Category Badge */}
                <div className="absolute top-2.5 right-2.5">
                  <span className="bg-white/90 backdrop-blur-sm text-gray-700 text-[11px] font-semibold px-2.5 py-1 rounded-lg border border-gray-200 shadow-sm">
                    {item.category}
                  </span>
                </div>
              </div>

              {/* Card Body */}
              <div className="p-4 flex-grow flex flex-col justify-between">
                <div>
                  <h3 className="font-bold text-gray-900 line-clamp-1 group-hover:text-blue-600 transition text-sm">
                    <a href={item.detail_url}>{item.title}</a>
                  </h3>
                  <div className="flex items-center text-xs text-gray-500 mt-2 space-x-1 space-x-reverse">
                    <svg className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                    <span className="truncate">{item.city}، {item.neighborhood || 'محدوده مشخص نشده'}</span>
                  </div>
                </div>

                {/* Price & Actions */}
                <div className="mt-4 pt-3 border-t border-gray-100 flex flex-col gap-2">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-gray-500">اجاره روزانه:</span>
                    <span className="text-sm font-bold text-gray-900">
                      {item.daily_price.toLocaleString('fa-IR')} <span className="text-[11px] font-normal text-gray-500">تومان</span>
                    </span>
                  </div>
                  {item.hourly_price && (
                    <div className="flex items-baseline justify-between text-xs text-gray-500">
                      <span>اجاره ساعتی:</span>
                      <span className="font-medium text-gray-700">
                        {item.hourly_price.toLocaleString('fa-IR')} تومان
                      </span>
                    </div>
                  )}

                  {/* Delivery & Link Button */}
                  <div className="flex items-center justify-between pt-2">
                    <div className="flex gap-1">
                      {item.allow_pickup && (
                        <span className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded border border-blue-100" title="تحویل حضوری">
                          حضوری
                        </span>
                      )}
                      {item.allow_courier && (
                        <span className="text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded border border-purple-100" title="ارسال با پیک">
                          پیک
                        </span>
                      )}
                    </div>
                    <a
                      href={item.detail_url}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-700 transition"
                    >
                      مشاهده ←
                    </a>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : !loading && (
        <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center max-w-lg mx-auto">
          <div className="w-16 h-16 bg-blue-50 text-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          </div>
          <h3 className="text-base font-bold text-gray-900 mb-1">کالایی یافت نشد</h3>
          <p className="text-xs text-gray-500 leading-relaxed mb-6">
            متأسفانه هیچ کالایی با فیلترهای انتخابی شما پیدا نشد. می‌توانید با حذف برخی فیلترها دوباره امتحان کنید.
          </p>
          <button
            type="button"
            onClick={handleClear}
            className="inline-flex items-center justify-center px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-sm transition"
          >
            مشاهده همه کالاها
          </button>
        </div>
      )}
    </div>
  );
}
