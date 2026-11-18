import React, { useState, useEffect } from 'react';
import { getCsrfToken } from '../utils/csrf';

export default function PricePreviewIsland({
  itemId,
  previewUrl = '/rentals/price-preview-json/',
  dailyPrice = 0,
  hourlyPrice = null,
  depositAmount = 0,
}) {
  const [startAt, setStartAt] = useState('');
  const [endAt, setEndAt] = useState('');
  const [loading, setLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [error, setError] = useState(null);

  // Sync with Django form inputs (#id_start_at and #id_end_at)
  useEffect(() => {
    const startInput = document.getElementById('id_start_at');
    const endInput = document.getElementById('id_end_at');

    const handleStartChange = () => {
      if (startInput) setStartAt(startInput.value);
    };
    const handleEndChange = () => {
      if (endInput) setEndAt(endInput.value);
    };

    if (startInput) {
      setStartAt(startInput.value);
      startInput.addEventListener('input', handleStartChange);
      startInput.addEventListener('change', handleStartChange);
    }
    if (endInput) {
      setEndAt(endInput.value);
      endInput.addEventListener('input', handleEndChange);
      endInput.addEventListener('change', handleEndChange);
    }

    return () => {
      if (startInput) {
        startInput.removeEventListener('input', handleStartChange);
        startInput.removeEventListener('change', handleStartChange);
      }
      if (endInput) {
        endInput.removeEventListener('input', handleEndChange);
        endInput.removeEventListener('change', handleEndChange);
      }
    };
  }, []);

  // Fetch price preview when startAt and endAt are present
  useEffect(() => {
    if (!startAt || !endAt) {
      setPreviewData(null);
      setError(null);
      return;
    }

    let isCancelled = false;

    const fetchPreview = async () => {
      setLoading(true);
      setError(null);
      try {
        const csrfToken = getCsrfToken();
        const res = await fetch(previewUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            item_id: itemId,
            start_at: startAt,
            end_at: endAt,
          }),
        });

        const data = await res.json();
        if (isCancelled) return;

        if (!res.ok || !data.valid) {
          setError(data.error || 'تاریخ‌های وارد شده نامعتبر هستند.');
          setPreviewData(null);
        } else {
          setPreviewData(data);
          setError(null);
        }
      } catch (err) {
        if (!isCancelled) {
          console.error('Price preview fetch error:', err);
          setError('خطا در محاسبه قیمت.');
          setPreviewData(null);
        }
      } finally {
        if (!isCancelled) setLoading(false);
      }
    };

    const timer = setTimeout(fetchPreview, 200);
    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [itemId, previewUrl, startAt, endAt]);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
      <div className="flex items-center justify-between border-b border-gray-100 pb-3">
        <h3 className="text-sm font-bold text-gray-900 flex items-center space-x-2 space-x-reverse">
          <span>پیش‌نمایش زنده قیمت</span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold">
            React Island
          </span>
        </h3>
        {loading && (
          <span className="text-xs text-blue-600 flex items-center space-x-1 space-x-reverse">
            <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>محاسبه...</span>
          </span>
        )}
      </div>

      {/* When dates are filled and valid preview is returned */}
      {previewData && (
        <div className="space-y-3">
          {/* Overlap alert */}
          {previewData.has_overlap && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs flex items-center space-x-2 space-x-reverse">
              <span className="text-base">⚠️</span>
              <div>
                <p className="font-bold">تداخل زمانی وجود دارد!</p>
                <p className="text-[11px] text-amber-700 mt-0.5">
                  کالا در این بازه زمانی دارای رزرو فعال دیگری است و ثبت درخواست ممکن است تایید نگردد.
                </p>
              </div>
            </div>
          )}

          {/* Pricing breakdown */}
          <div className="space-y-2 text-xs">
            <div className="flex justify-between items-center text-gray-600">
              <span>مدت زمان محاسبه‌شده:</span>
              <span className="font-semibold text-gray-800">
                {previewData.duration_days >= 1
                  ? `${previewData.duration_days} روز`
                  : `${previewData.duration_hours} ساعت`}
              </span>
            </div>

            <div className="flex justify-between items-center text-gray-600">
              <span>تعرفه اعمال‌شده:</span>
              <span className="font-medium text-gray-700">
                {previewData.pricing_type_display} ({previewData.unit_price.toLocaleString('fa-IR')} تومان × {previewData.units_billed} واحد)
              </span>
            </div>

            <div className="flex justify-between items-center text-gray-600 pt-2 border-t border-gray-100">
              <span>مبلغ اجاره:</span>
              <span className="font-bold text-gray-900">
                {previewData.rent_amount.toLocaleString('fa-IR')} تومان
              </span>
            </div>

            <div className="flex justify-between items-center text-gray-600">
              <span>مبلغ ودیعه امانت (قابل استرداد):</span>
              <span className="font-semibold text-gray-800">
                {previewData.deposit_amount > 0
                  ? `${previewData.deposit_amount.toLocaleString('fa-IR')} تومان`
                  : 'بدون ودیعه'}
              </span>
            </div>

            {/* Total */}
            <div className="pt-2 border-t border-gray-200 flex justify-between items-center bg-blue-50/70 p-3 rounded-xl text-blue-950 font-bold text-sm">
              <span>مجموع پرداختی:</span>
              <span className="text-base text-blue-700">
                {previewData.total_amount.toLocaleString('fa-IR')} تومان
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* Empty / Initial state */}
      {!previewData && !error && (
        <div className="text-xs text-gray-500 space-y-2 leading-relaxed">
          <p className="flex items-center space-x-1.5 space-x-reverse text-blue-600 font-medium">
            <span>💡</span>
            <span>راهنمای محاسبه قیمت:</span>
          </p>
          <p>
            با تکمیل تاریخ و ساعت تحویل و بازگرداندن، پیش‌فاکتور دقیق به صورت خودکار در این بخش محاسبه و به روز می‌شود.
          </p>
          <div className="pt-2 border-t border-gray-100 space-y-1.5 text-[11px] text-gray-400">
            <div className="flex justify-between">
              <span>تعرفه روزانه:</span>
              <span>{Number(dailyPrice).toLocaleString('fa-IR')} تومان</span>
            </div>
            {hourlyPrice && (
              <div className="flex justify-between">
                <span>تعرفه ساعتی:</span>
                <span>{Number(hourlyPrice).toLocaleString('fa-IR')} تومان</span>
              </div>
            )}
            <div className="flex justify-between">
              <span>ودیعه:</span>
              <span>{depositAmount > 0 ? `${Number(depositAmount).toLocaleString('fa-IR')} تومان` : 'بدون ودیعه'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
