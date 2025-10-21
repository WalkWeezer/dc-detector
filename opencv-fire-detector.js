// Улучшенный детектор огня с использованием OpenCV.js
class OpenCVFireDetector {
    constructor() {
        this.isOpenCVReady = false;
        this.video = null;
        this.cap = null;
        this.dst = null;
        this.mask = null;
        this.kernel = null;
        this.backgroundSubtractor = null;
        this.fireRegions = [];
        
        // Параметры детекции
        this.params = {
            // HSV диапазоны для огня
            lowerH: 0,
            upperH: 20,
            lowerS: 50,
            upperS: 255,
            lowerV: 50,
            upperV: 255,
            
            // Морфологические операции
            morphKernelSize: 5,
            minContourArea: 500,
            maxContourArea: 50000,
            
            // Детекция движения
            history: 500,
            varThreshold: 16,
            detectShadows: true
        };
    }
    
    // Инициализация OpenCV
    initOpenCV() {
        this.isOpenCVReady = true;
        console.log('OpenCV.js загружен и готов к работе');
        
        // Создаем объекты для обработки
        this.dst = new cv.Mat();
        this.mask = new cv.Mat();
        this.kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, 
            new cv.Size(this.params.morphKernelSize, this.params.morphKernelSize));
        
        // Создаем детектор движения
        this.backgroundSubtractor = cv.createBackgroundSubtractorMOG2(
            this.params.history, 
            this.params.varThreshold, 
            this.params.detectShadows
        );
    }
    
    // Основной метод детекции огня
    detectFire(frame) {
        if (!this.isOpenCVReady) return [];
        
        try {
            // Конвертируем в HSV
            cv.cvtColor(frame, this.dst, cv.COLOR_RGBA2RGB);
            cv.cvtColor(this.dst, this.dst, cv.COLOR_RGB2HSV);
            
            // Создаем маску для огня
            const lower = new cv.Scalar(this.params.lowerH, this.params.lowerS, this.params.lowerV);
            const upper = new cv.Scalar(this.params.upperH, this.params.upperS, this.params.upperV);
            cv.inRange(this.dst, lower, upper, this.mask);
            
            // Морфологические операции для очистки
            cv.morphologyEx(this.mask, this.mask, cv.MORPH_OPEN, this.kernel);
            cv.morphologyEx(this.mask, this.mask, cv.MORPH_CLOSE, this.kernel);
            
            // Находим контуры
            const contours = new cv.MatVector();
            const hierarchy = new cv.Mat();
            cv.findContours(this.mask, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);
            
            // Анализируем контуры
            const fireRegions = [];
            for (let i = 0; i < contours.size(); i++) {
                const contour = contours.get(i);
                const area = cv.contourArea(contour);
                
                if (area > this.params.minContourArea && area < this.params.maxContourArea) {
                    // Получаем ограничивающий прямоугольник
                    const rect = cv.boundingRect(contour);
                    
                    // Анализируем форму и движение
                    const aspectRatio = rect.width / rect.height;
                    const extent = area / (rect.width * rect.height);
                    
                    // Фильтруем по форме (огонь обычно вытянутый и неправильной формы)
                    if (aspectRatio > 0.3 && aspectRatio < 3.0 && extent < 0.8) {
                        // Анализируем движение в области
                        const motionScore = this.analyzeMotionInRegion(frame, rect);
                        
                        if (motionScore > 0.1) {
                            fireRegions.push({
                                rect: rect,
                                area: area,
                                aspectRatio: aspectRatio,
                                extent: extent,
                                motionScore: motionScore,
                                probability: this.calculateFireProbability(area, aspectRatio, extent, motionScore)
                            });
                        }
                    }
                }
            }
            
            // Очищаем память
            contours.delete();
            hierarchy.delete();
            
            return fireRegions;
            
        } catch (error) {
            console.error('Ошибка в детекции огня:', error);
            return [];
        }
    }
    
    // Анализ движения в области
    analyzeMotionInRegion(frame, rect) {
        if (!this.backgroundSubtractor) return 0;
        
        try {
            // Вырезаем область
            const roi = frame.roi(rect);
            const fgMask = new cv.Mat();
            
            // Применяем детектор движения
            this.backgroundSubtractor.apply(roi, fgMask);
            
            // Подсчитываем пиксели движения
            const motionPixels = cv.countNonZero(fgMask);
            const totalPixels = rect.width * rect.height;
            const motionRatio = motionPixels / totalPixels;
            
            // Очищаем память
            roi.delete();
            fgMask.delete();
            
            return motionRatio;
            
        } catch (error) {
            console.error('Ошибка в анализе движения:', error);
            return 0;
        }
    }
    
    // Вычисление вероятности огня
    calculateFireProbability(area, aspectRatio, extent, motionScore) {
        let probability = 0;
        
        // Размер области (30%)
        const sizeScore = Math.min(area / 10000, 1);
        probability += sizeScore * 0.3;
        
        // Соотношение сторон (20%)
        const aspectScore = aspectRatio > 0.5 && aspectRatio < 2.5 ? 1 : 0.5;
        probability += aspectScore * 0.2;
        
        // Форма (20%)
        const shapeScore = extent < 0.7 ? 1 : 0.3;
        probability += shapeScore * 0.2;
        
        // Движение (30%)
        probability += motionScore * 0.3;
        
        return Math.min(probability, 1);
    }
    
    // Обновление параметров
    updateParams(newParams) {
        this.params = { ...this.params, ...newParams };
        
        // Обновляем ядро морфологии
        if (this.kernel) {
            this.kernel.delete();
        }
        this.kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, 
            new cv.Size(this.params.morphKernelSize, this.params.morphKernelSize));
    }
    
    // Очистка ресурсов
    cleanup() {
        if (this.dst) this.dst.delete();
        if (this.mask) this.mask.delete();
        if (this.kernel) this.kernel.delete();
        if (this.backgroundSubtractor) this.backgroundSubtractor.delete();
    }
}

// Глобальная функция для инициализации OpenCV
function onOpenCvReady() {
    window.opencvFireDetector = new OpenCVFireDetector();
    window.opencvFireDetector.initOpenCV();
    
    // Уведомляем основной класс о готовности
    if (window.fireDetector) {
        window.fireDetector.onOpenCVReady();
    }
}

