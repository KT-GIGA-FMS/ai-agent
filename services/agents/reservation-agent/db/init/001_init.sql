-- 예약 시스템 데이터베이스 스키마 초기화

-- 차량 모델 테이블
CREATE TABLE IF NOT EXISTS car_models (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    fuel_type VARCHAR(20),
    fuel_efficiency VARCHAR(50),
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 차량 테이블
CREATE TABLE IF NOT EXISTS cars (
    id VARCHAR(50) PRIMARY KEY,
    car_model_id VARCHAR(50) NOT NULL REFERENCES car_models(id),
    status VARCHAR(20) DEFAULT 'available' CHECK (status IN ('available', 'maintenance', 'reserved')),
    car_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 예약 테이블
CREATE TABLE IF NOT EXISTS reservations (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    vehicle_id VARCHAR(50) NOT NULL REFERENCES cars(id),
    start_at TIMESTAMP WITH TIME ZONE NOT NULL,
    end_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled', 'completed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 제약조건
    CONSTRAINT valid_time_range CHECK (start_at < end_at)
);

-- 세션 테이블 (Redis 대체용, 선택사항)
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(50),
    chat_history JSONB,
    slots JSONB,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_cars_status ON cars(status);
CREATE INDEX IF NOT EXISTS idx_cars_model ON cars(car_model_id);
CREATE INDEX IF NOT EXISTS idx_reservations_user ON reservations(user_id);
CREATE INDEX IF NOT EXISTS idx_reservations_vehicle ON reservations(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_reservations_time ON reservations(start_at, end_at);
CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- 업데이트 트리거 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 생성
CREATE TRIGGER update_car_models_updated_at BEFORE UPDATE ON car_models
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cars_updated_at BEFORE UPDATE ON cars
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reservations_updated_at BEFORE UPDATE ON reservations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 샘플 데이터 삽입
INSERT INTO car_models (id, name, fuel_type, fuel_efficiency) VALUES
    ('model-1', 'Hyundai Avante', 'gasoline', '15.2 km/l'),
    ('model-2', 'Hyundai Sonata', 'gasoline', '14.8 km/l'),
    ('model-3', 'Kia K5', 'gasoline', '15.0 km/l'),
    ('model-4', 'Tesla Model 3', 'electric', '500 km/charge'),
    ('model-5', 'Hyundai Tucson', 'gasoline', '13.5 km/l')
ON CONFLICT (id) DO NOTHING;

INSERT INTO cars (id, car_model_id, status, car_type) VALUES
    ('uuid-1', 'model-1', 'available', 'sedan'),
    ('uuid-2', 'model-2', 'available', 'sedan'),
    ('uuid-3', 'model-3', 'available', 'sedan'),
    ('uuid-4', 'model-4', 'available', 'sedan'),
    ('uuid-5', 'model-5', 'available', 'suv')
ON CONFLICT (id) DO NOTHING;
