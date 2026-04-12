<?php

namespace App\Support;

class TimeConstant
{
    public const int HOUR_IN_SECONDS = 3600;
    public const int DAY_IN_SECONDS = 86400;
}

class CacheService
{
    public function hourlyTtl(): int
    {
        return TimeConstant::HOUR_IN_SECONDS;
    }

    public function dailyTtl(): int
    {
        return TimeConstant::DAY_IN_SECONDS;
    }
}
