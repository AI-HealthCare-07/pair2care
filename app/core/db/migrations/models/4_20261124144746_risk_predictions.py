from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `risk_predictions` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `disease` VARCHAR(12) NOT NULL COMMENT 'HYPERTENSION: HYPERTENSION\nDIABETES: DIABETES',
    `method` VARCHAR(16) NOT NULL COMMENT 'MODEL: MODEL\nCHECKUP_CRITERIA: CHECKUP_CRITERIA' DEFAULT 'MODEL',
    `score` SMALLINT,
    `level` VARCHAR(7) NOT NULL COMMENT 'LOW: LOW\nCAUTION: CAUTION\nHIGH: HIGH',
    `factors` JSON,
    `model_version` VARCHAR(50),
    `input_snapshot` JSON NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `checkup_record_id` BIGINT,
    `health_profile_id` BIGINT NOT NULL,
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_risk_pre_checkup__f276037c` FOREIGN KEY (`checkup_record_id`) REFERENCES `checkup_records` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_risk_pre_health_p_5917e7b1` FOREIGN KEY (`health_profile_id`) REFERENCES `health_profiles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_risk_pre_users_a6752cf4` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_risk_predic_user_id_e6638c` (`user_id`, `disease`, `created_at`)
) CHARACTER SET utf8mb4 COMMENT='예측 한 번 = 질환별 한 행 (기록용, 수정 없음). api.md 5-0·5-1.';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `risk_predictions`;"""


MODELS_STATE = (
    "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"
)
