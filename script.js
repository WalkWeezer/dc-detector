class FireDetector {
    constructor() {
        this.video = document.getElementById('video');
        this.canvas = document.getElementById('canvas');
        this.ctx = this.canvas.getContext('2d');
        
        // OpenCV детектор
        this.opencvDetector = null;
        this.useOpenCV = true;
        
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.captureBtn = document.getElementById('captureBtn');
        
        // Элементы настроек
        this.sensitivitySlider = document.getElementById('sensitivitySlider');
        this.sensitivityValue = document.getElementById('sensitivityValue');
        this.motionSlider = document.getElementById('motionSlider');
        this.motionValue = document.getElementById('motionValue');
        this.motionDetectionCheckbox = document.getElementById('motionDetection');
        this.showHighlightsCheckbox = document.getElementById('showHighlights');
        this.useOpenCVCheckbox = document.getElementById('useOpenCV');
        this.mergeDistanceSlider = document.getElementById('mergeDistanceSlider');
        this.mergeDistanceValue = document.getElementById('mergeDistanceValue');
        this.pixelThresholdSlider = document.getElementById('pixelThresholdSlider');
        this.pixelThresholdValue = document.getElementById('pixelThresholdValue');
        this.stabilityFramesSlider = document.getElementById('stabilityFramesSlider');
        this.stabilityFramesValue = document.getElementById('stabilityFramesValue');
        
        this.statusDot = document.querySelector('.status-dot');
        this.statusText = document.querySelector('.status-text');
        this.cameraStatus = document.getElementById('cameraStatus');
        this.resolution = document.getElementById('resolution');
        this.fps = document.getElementById('fps');
        this.detection = document.getElementById('detection');
        this.motionStatus = document.getElementById('motionStatus');
        this.fireRegionsCount = document.getElementById('fireRegionsCount');
        
        this.stream = null;
        this.isDetecting = false;
        this.frameCount = 0;
        this.lastTime = Date.now();
        this.fpsCounter = 0;
        
        // Настройки детекции
        this.sensitivity = 0.1; // Чувствительность (0.01 - 1.0)
        this.motionThreshold = 0.02; // Порог движения
        this.previousFrame = null;
        this.motionDetected = false;
        
        // Улучшенные настройки детекции движения
        this.motionHistory = []; // История кадров для анализа
        this.motionHistoryLength = 5; // Количество кадров для сравнения
        this.motionStabilityFrames = 3; // Минимум кадров с движением
        this.motionStabilityCounter = 0;
        this.pixelChangeThreshold = 15; // Порог изменения пикселя (уменьшен)
        
        this.init();
    }
    
    // Вызывается когда OpenCV готов
    onOpenCVReady() {
        this.opencvDetector = window.opencvFireDetector;
        console.log('OpenCV детектор готов к работе');
    }
    
    init() {
        this.setupEventListeners();
        this.updateStatus('disconnected', 'Камера отключена');
    }
    
    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startCamera());
        this.stopBtn.addEventListener('click', () => this.stopCamera());
        this.captureBtn.addEventListener('click', () => this.captureFrame());
        
        // Обработчики настроек
        this.sensitivitySlider.addEventListener('input', (e) => {
            this.sensitivity = parseFloat(e.target.value);
            this.sensitivityValue.textContent = this.sensitivity.toFixed(2);
        });
        
        this.motionSlider.addEventListener('input', (e) => {
            this.motionThreshold = parseFloat(e.target.value);
            this.motionValue.textContent = this.motionThreshold.toFixed(2);
        });
        
        this.motionDetectionCheckbox.addEventListener('change', (e) => {
            // Если отключили детекцию движения, сбрасываем предыдущий кадр
            if (!e.target.checked) {
                this.previousFrame = null;
            }
        });
        
        this.showHighlightsCheckbox.addEventListener('change', (e) => {
            // Если отключили выделения, очищаем их
            if (!e.target.checked) {
                this.clearFireRegions();
            }
        });
        
        this.useOpenCVCheckbox.addEventListener('change', (e) => {
            this.useOpenCV = e.target.checked;
            console.log('OpenCV режим:', this.useOpenCV ? 'включен' : 'отключен');
        });
        
        this.mergeDistanceSlider.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.mergeDistanceValue.textContent = `${Math.round(value * 100)}%`;
        });
        
        this.pixelThresholdSlider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            this.pixelChangeThreshold = value;
            this.pixelThresholdValue.textContent = value;
        });
        
        this.stabilityFramesSlider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            this.motionStabilityFrames = value;
            this.stabilityFramesValue.textContent = value;
        });
    }
    
    async startCamera() {
        try {
            this.updateStatus('connecting', 'Подключение к камере...');
            this.startBtn.disabled = true;
            
            // Запрашиваем доступ к камере
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    frameRate: { ideal: 30 }
                },
                audio: false
            });
            
            // Подключаем поток к видео элементу
            this.video.srcObject = this.stream;
            
            // Ждем загрузки метаданных
            this.video.addEventListener('loadedmetadata', () => {
                this.setupVideo();
                this.startDetection();
            });
            
        } catch (error) {
            console.error('Ошибка при запуске камеры:', error);
            this.updateStatus('error', 'Ошибка подключения к камере');
            this.startBtn.disabled = false;
            alert('Не удалось получить доступ к камере. Проверьте разрешения.');
        }
    }
    
    setupVideo() {
        const videoWidth = this.video.videoWidth;
        const videoHeight = this.video.videoHeight;
        
        // Настраиваем canvas для обработки кадров
        this.canvas.width = videoWidth;
        this.canvas.height = videoHeight;
        
        // Обновляем информацию о разрешении
        this.resolution.textContent = `${videoWidth}x${videoHeight}`;
        this.cameraStatus.textContent = 'Подключена';
        
        this.updateStatus('connected', 'Камера активна');
        this.startBtn.disabled = true;
        this.stopBtn.disabled = false;
        this.captureBtn.disabled = false;
    }
    
    startDetection() {
        this.isDetecting = true;
        this.detection.textContent = 'Активно';
        this.updateStatus('detecting', 'Анализ видео...');
        this.processFrame();
    }
    
    processFrame() {
        if (!this.isDetecting) {
            return;
        }
        
        // Проверяем, что видео готово к воспроизведению
        if (this.video.readyState < 2) {
            // Видео еще не готово, повторяем через 100мс
            setTimeout(() => this.processFrame(), 100);
            return;
        }
        
        // Обновляем счетчик FPS
        this.updateFPS();
        
        // Копируем кадр на canvas для обработки
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        // Получаем данные изображения для анализа
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        
        // Детекция движения (если включена)
        this.motionDetected = this.motionDetectionCheckbox.checked ? this.detectMotion(imageData) : true;
        
        // Обновляем статус движения
        this.motionStatus.textContent = this.motionDetected ? 'Да' : 'Нет';
        
        // Анализ огня только при наличии движения (или если детекция отключена)
        if (this.motionDetected) {
            let fireRegions = [];
            
            if (this.useOpenCV && this.opencvDetector) {
                // Используем OpenCV для более точного анализа
                fireRegions = this.analyzeFrameWithOpenCV(imageData);
            } else {
                // Используем старый алгоритм как fallback
                fireRegions = this.analyzeFrame(imageData);
            }
            
            this.fireRegionsCount.textContent = fireRegions.length;
            
            if (this.showHighlightsCheckbox.checked) {
                this.drawFireRegions(fireRegions);
            }
        } else {
            this.hideFireAlert();
            this.clearFireRegions();
            this.fireRegionsCount.textContent = '0';
        }
        
        // Сохраняем текущий кадр для следующего сравнения
        this.previousFrame = new Uint8ClampedArray(imageData.data);
        
        // Запрашиваем следующий кадр
        requestAnimationFrame(() => this.processFrame());
    }
    
    analyzeFrame(imageData) {
        const data = imageData.data;
        const width = imageData.width;
        const height = imageData.height;
        let firePixels = 0;
        let totalPixels = data.length / 4;
        const fireRegions = [];
        
        // Улучшенный алгоритм распознавания огня
        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            
            // Конвертируем RGB в HSV для лучшего анализа цветов
            const hsv = this.rgbToHsv(r, g, b);
            const h = hsv.h;
            const s = hsv.s;
            const v = hsv.v;
            
            // Критерии для обнаружения огня в HSV пространстве
            const isFireColor = (
                // Красный/оранжевый диапазон (0-60 градусов)
                (h >= 0 && h <= 60) &&
                // Высокая насыщенность
                s >= 0.5 &&
                // Достаточная яркость
                v >= 0.3
            );
            
            // Дополнительные RGB критерии для надежности
            const isFireRGB = (
                r > 100 && 
                g < r * 0.8 && 
                b < r * 0.6 &&
                r > g + 30
            );
            
            if (isFireColor && isFireRGB) {
                firePixels++;
                // Вычисляем координаты пикселя
                const pixelIndex = i / 4;
                const x = pixelIndex % width;
                const y = Math.floor(pixelIndex / width);
                fireRegions.push({ x, y, intensity: (r + g + b) / 3 });
            }
        }
        
        const firePercentage = (firePixels / totalPixels) * 100;
        
        // Адаптивный порог с учетом чувствительности
        const threshold = this.sensitivity * (totalPixels > 100000 ? 0.05 : 0.1);
        
        if (firePercentage > threshold) {
            this.showFireAlert(firePercentage);
            return this.groupFireRegions(fireRegions, width, height);
        } else {
            this.hideFireAlert();
            return [];
        }
    }
    
    // Конвертация RGB в HSV
    rgbToHsv(r, g, b) {
        r /= 255;
        g /= 255;
        b /= 255;
        
        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const diff = max - min;
        
        let h = 0;
        if (diff !== 0) {
            if (max === r) {
                h = ((g - b) / diff) % 6;
            } else if (max === g) {
                h = (b - r) / diff + 2;
            } else {
                h = (r - g) / diff + 4;
            }
        }
        h = Math.round(h * 60);
        if (h < 0) h += 360;
        
        const s = max === 0 ? 0 : diff / max;
        const v = max;
        
        return { h, s, v };
    }
    
    // Группировка пикселей огня в области
    groupFireRegions(firePixels, width, height) {
        if (firePixels.length === 0) return [];
        
        const regions = [];
        const visited = new Set();
        const minRegionSize = 20; // Уменьшаем минимальный размер для первичной группировки
        
        // Первичная группировка пикселей
        for (const pixel of firePixels) {
            const key = `${pixel.x},${pixel.y}`;
            if (visited.has(key)) continue;
            
            const region = this.floodFill(firePixels, pixel, visited, width, height);
            if (region.length >= minRegionSize) {
                // Вычисляем вероятность для области
                const probability = this.calculateFireProbability(region);
                regions.push({
                    pixels: region,
                    probability: probability,
                    size: region.length,
                    center: this.calculateCenter(region)
                });
            }
        }
        
        // Объединяем близкие области
        return this.mergeNearbyRegions(regions, width, height);
    }
    
    // Вычисление центра области
    calculateCenter(region) {
        if (region.length === 0) return { x: 0, y: 0 };
        
        const sumX = region.reduce((sum, p) => sum + p.x, 0);
        const sumY = region.reduce((sum, p) => sum + p.y, 0);
        
        return {
            x: sumX / region.length,
            y: sumY / region.length
        };
    }
    
    // Объединение близких областей
    mergeNearbyRegions(regions, width, height) {
        if (regions.length <= 1) return regions;
        
        const mergedRegions = [];
        const used = new Set();
        const mergeDistancePercent = parseFloat(this.mergeDistanceSlider.value);
        const mergeDistance = Math.min(width, height) * mergeDistancePercent;
        
        for (let i = 0; i < regions.length; i++) {
            if (used.has(i)) continue;
            
            const currentRegion = regions[i];
            const mergedRegion = {
                pixels: [...currentRegion.pixels],
                probability: currentRegion.probability,
                size: currentRegion.size,
                center: currentRegion.center
            };
            
            used.add(i);
            
            // Ищем близкие области для объединения
            for (let j = i + 1; j < regions.length; j++) {
                if (used.has(j)) continue;
                
                const otherRegion = regions[j];
                const distance = this.calculateDistance(currentRegion.center, otherRegion.center);
                
                if (distance <= mergeDistance) {
                    // Объединяем области
                    mergedRegion.pixels.push(...otherRegion.pixels);
                    mergedRegion.size += otherRegion.size;
                    
                    // Пересчитываем центр
                    mergedRegion.center = this.calculateCenter(mergedRegion.pixels);
                    
                    // Пересчитываем вероятность (взвешенное среднее)
                    const totalSize = currentRegion.size + otherRegion.size;
                    mergedRegion.probability = (
                        currentRegion.probability * currentRegion.size +
                        otherRegion.probability * otherRegion.size
                    ) / totalSize;
                    
                    used.add(j);
                }
            }
            
            // Фильтруем по минимальному размеру после объединения
            if (mergedRegion.size >= 50) {
                mergedRegions.push(mergedRegion);
            }
        }
        
        return mergedRegions;
    }
    
    // Вычисление расстояния между центрами областей
    calculateDistance(center1, center2) {
        const dx = center1.x - center2.x;
        const dy = center1.y - center2.y;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    // Вычисление вероятности того, что область является огнем
    calculateFireProbability(region) {
        if (region.length === 0) return 0;
        
        let totalIntensity = 0;
        let colorScore = 0;
        let motionScore = 0;
        
        // Анализируем каждый пиксель в области
        for (const pixel of region) {
            totalIntensity += pixel.intensity || 0;
            
            // Простая оценка на основе интенсивности
            if (pixel.intensity > 150) colorScore += 1;
            else if (pixel.intensity > 100) colorScore += 0.5;
        }
        
        // Нормализуем оценки
        const avgIntensity = totalIntensity / region.length;
        const normalizedColorScore = Math.min(colorScore / region.length, 1);
        
        // Размер области влияет на вероятность
        const sizeScore = Math.min(region.length / 1000, 1); // Нормализуем к 1000 пикселей
        
        // Формируем финальную вероятность
        const probability = (
            normalizedColorScore * 0.4 +  // Цвет (40%)
            sizeScore * 0.3 +             // Размер (30%)
            (avgIntensity / 255) * 0.3    // Интенсивность (30%)
        );
        
        return Math.min(Math.max(probability, 0), 1); // Ограничиваем 0-1
    }
    
    // Анализ кадра с использованием OpenCV
    analyzeFrameWithOpenCV(imageData) {
        if (!this.opencvDetector) return [];
        
        try {
            // Создаем Mat из ImageData
            const src = cv.matFromImageData(imageData);
            
            // Детектируем огонь
            const fireRegions = this.opencvDetector.detectFire(src);
            
            // Конвертируем в формат для отображения
            const regions = fireRegions.map(region => ({
                pixels: [], // OpenCV не возвращает пиксели
                probability: region.probability,
                size: region.area,
                rect: region.rect,
                center: {
                    x: region.rect.x + region.rect.width / 2,
                    y: region.rect.y + region.rect.height / 2
                }
            }));
            
            // Очищаем память
            src.delete();
            
            return regions;
            
        } catch (error) {
            console.error('Ошибка в OpenCV анализе:', error);
            return [];
        }
    }
    
    // Алгоритм заливки для группировки соседних пикселей
    floodFill(firePixels, startPixel, visited, width, height) {
        const region = [];
        const stack = [startPixel];
        const pixelSet = new Set(firePixels.map(p => `${p.x},${p.y}`));
        
        while (stack.length > 0) {
            const pixel = stack.pop();
            const key = `${pixel.x},${pixel.y}`;
            
            if (visited.has(key) || !pixelSet.has(key)) continue;
            
            visited.add(key);
            region.push(pixel);
            
            // Добавляем соседние пиксели
            const neighbors = [
                { x: pixel.x - 1, y: pixel.y },
                { x: pixel.x + 1, y: pixel.y },
                { x: pixel.x, y: pixel.y - 1 },
                { x: pixel.x, y: pixel.y + 1 }
            ];
            
            for (const neighbor of neighbors) {
                if (neighbor.x >= 0 && neighbor.x < width && 
                    neighbor.y >= 0 && neighbor.y < height) {
                    stack.push(neighbor);
                }
            }
        }
        
        return region;
    }
    
    // Отрисовка областей огня на видео
    drawFireRegions(regions) {
        // Очищаем предыдущие выделения
        this.clearFireRegions();
        
        if (regions.length === 0) return;
        
        // Создаем overlay для выделений
        let overlay = document.querySelector('.fire-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'fire-overlay';
            overlay.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 15;
            `;
            document.querySelector('.video-container').appendChild(overlay);
        }
        
        // Очищаем предыдущие выделения
        overlay.innerHTML = '';
        
        // Рисуем каждую область
        regions.forEach((regionData, index) => {
            let minX, maxX, minY, maxY;
            
            if (regionData.rect) {
                // OpenCV данные - используем прямоугольник
                minX = regionData.rect.x;
                maxX = regionData.rect.x + regionData.rect.width;
                minY = regionData.rect.y;
                maxY = regionData.rect.y + regionData.rect.height;
            } else if (regionData.pixels && regionData.pixels.length > 0) {
                // Старый алгоритм - вычисляем границы
                const xs = regionData.pixels.map(p => p.x);
                const ys = regionData.pixels.map(p => p.y);
                minX = Math.min(...xs);
                maxX = Math.max(...xs);
                minY = Math.min(...ys);
                maxY = Math.max(...ys);
            } else {
                return; // Пропускаем пустые области
            }
            
            // Определяем цвет рамки на основе вероятности
            const probability = regionData.probability;
            let borderColor, bgColor, shadowColor;
            
            if (probability > 0.7) {
                borderColor = '#ff0000'; // Красный - высокая вероятность
                bgColor = 'rgba(255, 0, 0, 0.15)';
                shadowColor = 'rgba(255, 0, 0, 0.6)';
            } else if (probability > 0.4) {
                borderColor = '#ff8800'; // Оранжевый - средняя вероятность
                bgColor = 'rgba(255, 136, 0, 0.15)';
                shadowColor = 'rgba(255, 136, 0, 0.6)';
            } else {
                borderColor = '#ffaa00'; // Желтый - низкая вероятность
                bgColor = 'rgba(255, 170, 0, 0.15)';
                shadowColor = 'rgba(255, 170, 0, 0.6)';
            }
            
            // Создаем элемент выделения
            const highlight = document.createElement('div');
            highlight.className = 'fire-highlight';
            highlight.style.cssText = `
                position: absolute;
                left: ${(minX / this.canvas.width) * 100}%;
                top: ${(minY / this.canvas.height) * 100}%;
                width: ${((maxX - minX) / this.canvas.width) * 100}%;
                height: ${((maxY - minY) / this.canvas.height) * 100}%;
                border: 2px solid ${borderColor};
                border-radius: 4px;
                background: ${bgColor};
                animation: firePulse 1.5s infinite;
                box-shadow: 0 0 15px ${shadowColor};
            `;
            
            // Добавляем подпись с вероятностью
            const label = document.createElement('div');
            const probabilityPercent = Math.round(probability * 100);
            label.textContent = `🔥 ${probabilityPercent}%`;
            label.style.cssText = `
                position: absolute;
                top: -20px;
                left: 0;
                background: ${borderColor};
                color: white;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                min-width: 40px;
                text-align: center;
            `;
            highlight.appendChild(label);
            
            overlay.appendChild(highlight);
        });
        
        // Добавляем CSS анимацию если её нет
        if (!document.querySelector('#fire-highlight-styles')) {
            const style = document.createElement('style');
            style.id = 'fire-highlight-styles';
            style.textContent = `
                @keyframes firePulse {
                    0% { 
                        opacity: 0.8;
                        transform: scale(1);
                    }
                    50% { 
                        opacity: 1;
                        transform: scale(1.02);
                    }
                    100% { 
                        opacity: 0.8;
                        transform: scale(1);
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    // Очистка выделений
    clearFireRegions() {
        const overlay = document.querySelector('.fire-overlay');
        if (overlay) {
            overlay.innerHTML = '';
        }
    }
    
    // Улучшенная детекция движения с историей кадров
    detectMotion(currentImageData) {
        const currentData = currentImageData.data;
        const totalPixels = currentData.length / 4;
        
        // Добавляем текущий кадр в историю
        this.motionHistory.push(new Uint8ClampedArray(currentData));
        
        // Ограничиваем размер истории
        if (this.motionHistory.length > this.motionHistoryLength) {
            this.motionHistory.shift();
        }
        
        // Нужно минимум 2 кадра для анализа
        if (this.motionHistory.length < 2) {
            return true; // Первые кадры - считаем что есть движение
        }
        
        // Анализируем движение по нескольким кадрам
        const motionScores = [];
        
        // Сравниваем текущий кадр с предыдущими
        for (let i = 0; i < this.motionHistory.length - 1; i++) {
            const previousData = this.motionHistory[i];
            let changedPixels = 0;
            
            // Сравниваем пиксели с учетом малых амплитуд
            for (let j = 0; j < currentData.length; j += 4) {
                const rDiff = Math.abs(currentData[j] - previousData[j]);
                const gDiff = Math.abs(currentData[j + 1] - previousData[j + 1]);
                const bDiff = Math.abs(currentData[j + 2] - previousData[j + 2]);
                
                // Более чувствительный порог для малых изменений
                if (rDiff > this.pixelChangeThreshold || 
                    gDiff > this.pixelChangeThreshold || 
                    bDiff > this.pixelChangeThreshold) {
                    changedPixels++;
                }
            }
            
            const motionPercentage = changedPixels / totalPixels;
            motionScores.push(motionPercentage);
        }
        
        // Вычисляем средний уровень движения
        const avgMotion = motionScores.reduce((sum, score) => sum + score, 0) / motionScores.length;
        
        // Определяем, есть ли устойчивое движение
        const hasMotion = avgMotion > this.motionThreshold;
        
        if (hasMotion) {
            this.motionStabilityCounter++;
        } else {
            this.motionStabilityCounter = Math.max(0, this.motionStabilityCounter - 1);
        }
        
        // Движение считается детектированным только после нескольких кадров
        return this.motionStabilityCounter >= this.motionStabilityFrames;
    }
    
    showFireAlert(percentage) {
        // Добавляем визуальное предупреждение
        if (!document.querySelector('.fire-alert')) {
            const alert = document.createElement('div');
            alert.className = 'fire-alert';
            alert.innerHTML = `
                <div class="alert-content">
                    <span class="alert-icon">🔥</span>
                    <span class="alert-text">Очаг обнаружен!</span>
                    <span class="alert-percentage">${percentage.toFixed(1)}%</span>
                </div>
            `;
            
            // Добавляем стили для предупреждения (маленький в углу)
            alert.style.cssText = `
                position: absolute;
                top: 10px;
                right: 10px;
                background: rgba(255, 0, 0, 0.9);
                color: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-weight: bold;
                text-align: center;
                z-index: 20;
                animation: fireAlert 0.5s ease-in-out;
                font-size: 12px;
                min-width: 120px;
            `;
            
            document.querySelector('.video-container').appendChild(alert);
            
            // Добавляем CSS анимацию
            if (!document.querySelector('#fire-alert-styles')) {
                const style = document.createElement('style');
                style.id = 'fire-alert-styles';
                style.textContent = `
                    @keyframes fireAlert {
                        0% { transform: scale(0); }
                        50% { transform: scale(1.1); }
                        100% { transform: scale(1); }
                    }
                    .alert-content {
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        gap: 4px;
                    }
                    .alert-icon {
                        font-size: 1.2rem;
                        animation: pulse 1s infinite;
                    }
                    .alert-text {
                        font-size: 11px;
                    }
                    .alert-percentage {
                        font-size: 10px;
                        opacity: 0.9;
                    }
                `;
                document.head.appendChild(style);
            }
        }
    }
    
    hideFireAlert() {
        const alert = document.querySelector('.fire-alert');
        if (alert) {
            alert.remove();
        }
    }
    
    updateFPS() {
        this.frameCount++;
        const currentTime = Date.now();
        
        if (currentTime - this.lastTime >= 1000) {
            this.fpsCounter = this.frameCount;
            this.fps.textContent = this.fpsCounter;
            this.frameCount = 0;
            this.lastTime = currentTime;
        }
    }
    
    updateStatus(status, text) {
        this.statusText.textContent = text;
        this.statusDot.className = 'status-dot';
        
        switch (status) {
            case 'connecting':
                this.statusDot.classList.add('loading');
                break;
            case 'connected':
                this.statusDot.classList.add('connected');
                break;
            case 'detecting':
                this.statusDot.classList.add('detecting');
                break;
            case 'error':
                this.statusDot.style.background = '#ff6b6b';
                break;
            default:
                this.statusDot.style.background = '#ff6b6b';
        }
    }
    
    captureFrame() {
        if (!this.video.videoWidth) return;
        
        // Создаем ссылку для скачивания снимка
        const link = document.createElement('a');
        link.download = `fire-detection-${new Date().toISOString().slice(0,19)}.png`;
        link.href = this.canvas.toDataURL();
        link.click();
    }
    
    stopCamera() {
        this.isDetecting = false;
        
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.video.srcObject = null;
        this.hideFireAlert();
        this.clearFireRegions();
        
        // Сбрасываем историю движения
        this.motionHistory = [];
        this.motionStabilityCounter = 0;
        this.previousFrame = null;
        
        this.updateStatus('disconnected', 'Камера отключена');
        this.cameraStatus.textContent = 'Отключена';
        this.resolution.textContent = '-';
        this.fps.textContent = '-';
        this.detection.textContent = 'Не активно';
        this.motionStatus.textContent = 'Нет';
        this.fireRegionsCount.textContent = '0';
        
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        this.captureBtn.disabled = true;
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    new FireDetector();
});

// Обработка ошибок
window.addEventListener('error', (event) => {
    console.error('Ошибка:', event.error);
});

// Обработка необработанных промисов
window.addEventListener('unhandledrejection', (event) => {
    console.error('Необработанная ошибка промиса:', event.reason);
});
